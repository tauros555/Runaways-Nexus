from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from modules.training_radar import load_training
from modules.pedigree_core import load_masters, evaluate_pedigree_core
from modules.partner_compatibility import anchor_candidates, rank_partners
from modules.nexus_partner_v4 import build_partner_recommendations
from modules.race_development_core import load_rd_data, run_race_development
from modules.nexus_probability import calculate_base_scores, apply_surface_adjustment
from modules.day_bias import estimate_same_day_bias, add_bias_fit
from modules.odds import fetch_win_odds
from modules.value import add_value_metrics
from modules.jra_track import fetch_jra_track_conditions, cushion_to_nexus_band
from modules.m_bloodline import load_m_bundle, evaluate_m, attach_m_signature, add_distance_m
from modules.m_autogen import ensure_current_horses
from modules.data_refresh import dataset_status, dataset_signature, sync_inbox
from modules.crown_rules import add_crown_flags
from rd_modules.route_bias import render_route_grid

BASE=Path(__file__).resolve().parent
DATA=BASE/"data"/"training_current.csv"
A3_HISTORY=BASE/"data"/"a3_history.csv"
HEADER_IMAGE=BASE/"assets"/"runaways_nexus_header.jpeg"

st.set_page_config(page_title="Runaway's Nexus",page_icon="🏇",layout="wide")

st.markdown("""
<style>
.stApp{background:#061525;color:#eef6ff}
[data-testid='stSidebar']{background:#081c30}
.n-title{font-size:34px;font-weight:900;color:#f6fbff;margin-bottom:0}
.n-sub{color:#7fd7f5;margin-top:0}
.pick{border:1px solid #2e95b8;border-radius:14px;padding:14px 16px;margin:8px 0;background:#08233a}
.pick-hot{border-color:#49b889}
.tag{display:inline-block;padding:3px 8px;border-radius:8px;margin:2px 4px 2px 0;background:#0d3a4e;border:1px solid #2e95b8;font-size:12px}
.tag-good{background:#103c32;border-color:#3ab67f}
.tag-warn{background:#3d2d10;border-color:#d99f34}
.tag-bad{background:#3c1720;border-color:#d35e70}
.tag-crown{background:#4a3a08;border-color:#e3bd43;color:#fff4b0;font-weight:900}
.crown-mark{font-size:20px;font-weight:900;color:#ffd75e;margin-right:6px}
.small{font-size:12px;opacity:.78}
[data-testid='stMetric']{background:#08233a;border:1px solid #1f7ea5;border-radius:12px;padding:8px}
div.stButton>button{border:1px solid #2e95b8;border-radius:10px;background:#0b2941;color:#f5fbff;font-weight:700}
[data-testid='stImage'] img{border-radius:14px;border:1px solid #1f7ea5}
</style>
""",unsafe_allow_html=True)

if HEADER_IMAGE.exists():
    st.image(str(HEADER_IMAGE), use_container_width=True)
else:
    st.markdown("<p class='n-title'>Runaway’s Nexus</p><p class='n-sub'>Training × M Bloodline × Race Development × Track × Odds</p>",unsafe_allow_html=True)

def _positive(v):
    s=str(v).strip().lower()
    return s in {"1","true","yes","有","あり","〇","○","◎","★"}

def _file_signature(path: Path) -> str:
    """
    canonical CSVの更新を確実に検知するための軽量シグネチャ。
    mtime_ns + size を使用。ファイルが無い場合も状態をキー化する。
    """
    try:
        stt=path.stat()
        return f"{path.name}:{stt.st_mtime_ns}:{stt.st_size}"
    except FileNotFoundError:
        return f"{path.name}:missing"

def _training_signature() -> str:
    return "|".join([
        _file_signature(DATA),
        _file_signature(A3_HISTORY),
    ])

@st.cache_data(show_spinner=False)
def get_training(signature=None):
    # signature は Streamlit のキャッシュキーに含める。
    # 引数名を "_" で始めると Streamlit がハッシュ対象から除外するため、
    # 更新済みCSVを読まず古いDataFrameが残る。
    return load_training(DATA,A3_HISTORY)

@st.cache_data(show_spinner="M血統マスタ読込中...")
def get_m(signature=None):
    # generated_runner_m.csv 等の更新時も自動でキャッシュを切り替える。
    return load_m_bundle()

@st.cache_data(show_spinner="血統マスタ読込中...")
def get_pedigree():
    return load_masters()

@st.cache_data(show_spinner="Race Simulator履歴読込中...")
def get_rd(signature=None):
    # history_seed 等の更新時も自動でキャッシュを切り替える。
    return load_rd_data()

def race_selector(df,key="race_select"):
    x=df[["年月日","場所","R","レース名","芝・ダ","距離"]].copy()
    x["年月日"]=pd.to_numeric(x["年月日"],errors="coerce")
    x["R"]=pd.to_numeric(x["R"],errors="coerce")
    x["距離"]=pd.to_numeric(x["距離"],errors="coerce")
    x=x[x["年月日"].between(20000101,20991231)&x["R"].between(1,12)]
    x=x.groupby(["年月日","場所","R"],as_index=False).agg(
        {"レース名":"first","芝・ダ":"first","距離":"first"}
    ).sort_values(["年月日","場所","R"],ascending=[False,True,True])
    opts=[]; labels={}
    for _,r in x.iterrows():
        o=(int(r["年月日"]),str(r["場所"]),int(r["R"]))
        opts.append(o)
        ds=str(o[0]); d=f"{ds[:4]}/{ds[4:6]}/{ds[6:]}"
        labels[o]=f"{d} {o[1]}{o[2]}R {r['芝・ダ']}{int(r['距離'])}m {r['レース名']}"
    if not opts:
        return None,None,None,df.iloc[:0]
    sel=st.selectbox("レース選択",opts,format_func=lambda z:labels[z],key=key)
    d,p,r=sel
    cur=df[(pd.to_numeric(df["年月日"],errors="coerce")==d)&
           (df["場所"].astype(str)==p)&(pd.to_numeric(df["R"],errors="coerce")==r)].copy().sort_values("馬番")
    return d,p,r,cur

def training_flags(r):
    """通常A3と高勝率A3を独立した判定として保持する。"""
    return {
        "通常A3":_positive(r.get("A3LAP判定","")),
        "高勝率A3":_positive(r.get("A3高勝率Lap","")),
        "調教師判定":_positive(r.get("調教師判定","")),
        "調教コース":bool(r.get("course_badge",False)),
        "B3":bool(r.get("b3_badge",False)),
        "地雷":bool(r.get("jirai_badge",False)),
    }

def training_mark(r):
    f=training_flags(r)
    if f["地雷"]: return "×"
    if f["高勝率A3"] and f["調教師判定"]: return "◎"
    if f["高勝率A3"]: return "高A3"
    if f["調教師判定"]: return "調◎"
    if f["通常A3"]: return "A3"
    if f["B3"] or f["調教コース"]: return "○"
    return "－"

def detail_training(r):
    f=training_flags(r); tags=[]
    if f["調教師判定"]: tags.append("調教師◎")
    if f["高勝率A3"]: tags.append("高勝率A3")
    if f["通常A3"]: tags.append("通常A3")
    if f["B3"]: tags.append("B3")
    if f["調教コース"]: tags.append("調教コース◎")
    if f["地雷"]: tags.append("地雷×")
    return " / ".join(tags) if tags else "－"

def scenario_jp(code):
    return {"SLOW":"S","EVEN":"M","HIGH":"H","SPRINT_FINISH":"上がり勝負","LONG_SPURT":"ロンスパ"}.get(str(code),str(code))

def expected_market(odds):
    o=pd.to_numeric(odds,errors="coerce")
    inv=1/o
    return inv/inv.sum() if inv.notna().any() else pd.Series(np.nan,index=o.index)

# ---------------------------------------------------------
# DATA
# ---------------------------------------------------------
# Existing external updater can overwrite canonical files directly.
# If it drops newer files into data/inbox, import them automatically at app startup.
auto_import_messages=sync_inbox()

# sync_inbox() 後のファイル状態でシグネチャを作る。
# training_current.csv / a3_history.csv は専用シグネチャで即時更新を検知。
data_sig=dataset_signature()
training_sig=_training_signature()

df=get_training(training_sig)
mb=get_m(data_sig)

# ---------------------------------------------------------
# 0. DATA UPDATE STATUS / AUTO RELOAD
# ---------------------------------------------------------
st.markdown("## データ更新状況")
if auto_import_messages:
    for _msg in auto_import_messages:
        if "取込完了" in _msg:
            st.success("自動取込: " + _msg)
ds=dataset_status()
c1,c2=st.columns([4,1])
with c1:
    st.dataframe(ds[["データ","状態","更新日時","経過時間","サイズMB"]],use_container_width=True,hide_index=True)
with c2:
    st.metric("読込可能",f"{int((ds['状態']=='OK').sum())}/{len(ds)}")
    if st.button("🔄 更新確認・再読込",use_container_width=True,key="data_refresh"):
        msgs=sync_inbox()

        # canonical CSV更新後にメモリ上のDataFrameを強制破棄。
        get_training.clear()
        get_m.clear()
        get_pedigree.clear()
        get_rd.clear()

        if msgs:
            for msg in msgs:
                st.caption(msg)

        # rerun後は新しいファイルシグネチャで必ず再読込される。
        st.rerun()
st.caption("canonical CSVの更新時刻・サイズをキャッシュキーとして監視します。UPDATE_NEXUS後はアプリ再起動不要で、画面rerunまたは「更新確認・再読込」で最新CSVへ切り替わります。data/inbox への新ファイル投入にも対応します。")
st.divider()

# ---------------------------------------------------------
# 1. TODAY'S NEXUS PICK
# ---------------------------------------------------------
st.markdown("## TODAY’S NEXUS PICK / 注目レース")
dates=sorted(pd.to_numeric(df["年月日"],errors="coerce").dropna().astype(int).unique(),reverse=True)
pick_date=st.selectbox("注目開催日",dates,index=0,key="pick_date") if dates else None
day=df[pd.to_numeric(df["年月日"],errors="coerce").eq(pick_date)].copy() if pick_date else df.iloc[:0].copy()

# 1レース=1カード。該当馬が複数いても同じカード内へまとめる。
race_cards={}
if not day.empty:
    for (place,rno),g in day.groupby(["場所","R"],sort=True):
        surface=str(g["芝・ダ"].iloc[0]); distance=int(pd.to_numeric(g["距離"],errors="coerce").iloc[0])
        race_name=str(g["レース名"].iloc[0])
        me=evaluate_m(g,place,distance,surface,bundle=mb)
        gg=g.merge(me,on="馬番",how="left")
        gg=add_crown_flags(gg)
        horses=[]
        for _,r in gg.iterrows():
            crown_reasons=[z.strip() for z in str(r.get("crown_reasons","")).split("/") if z.strip()]
            reasons=[]
            if _positive(r.get("A3高勝率Lap","")):
                reasons.append("高勝率A3")
            if bool(r.get("M_STRICT_110",False)):
                raw=str(r.get("M_STRICT_REASON","M×コース◎"))
                reasons.extend([z.strip() for z in raw.split("/") if z.strip()])
            reasons=list(dict.fromkeys(reasons))
            if crown_reasons or reasons:
                horses.append({
                    "row":r,
                    "reasons":reasons,
                    "crown_reasons":crown_reasons,
                    "crown_mark":str(r.get("crown_mark","") or ""),
                })
        if horses:
            race_cards[(str(place),int(rno))]={
                "place":str(place),"rno":int(rno),"race_name":race_name,
                "surface":surface,"distance":distance,"horses":horses
            }

if not race_cards:
    st.info("この開催日に正式採用済みの注目条件該当馬はありません。")
else:
    top_odds_cache={}
    for (place,rno),card in race_cards.items():
        rg=day[(day["場所"].astype(str)==place)&(pd.to_numeric(day["R"],errors="coerce")==rno)]
        horses=[{"horse_no":int(z["馬番"]),"horse_name":str(z["馬名"])}
                for _,z in rg.iterrows() if pd.notna(z.get("馬番"))]
        try:
            od,_=fetch_win_odds(pick_date,place,rno,horses,force_update=False)
        except Exception:
            od={}
        top_odds_cache[(place,rno)]=od if isinstance(od,dict) else {}

    for (place,rno),card in race_cards.items():
        horse_html=[]
        race_odds=top_odds_cache.get((place,rno),{})
        for item in card["horses"]:
            r=item["row"]; reasons=item["reasons"]
            crown_reasons=item.get("crown_reasons",[])
            crown_mark=item.get("crown_mark","")
            hdata=race_odds.get(int(r["馬番"]),{})
            hdata=hdata if isinstance(hdata,dict) else {}
            od=hdata.get("odds")
            odds_text=f"{float(od):.1f}倍" if od is not None else "未取得"
            crown_tags="".join(f"<span class='tag tag-crown'>👑 {z}</span>" for z in crown_reasons)
            tags="".join(f"<span class='tag tag-good'>{z}</span>" for z in reasons)
            trainer_name=str(r.get("調教師","") or "").strip()
            jockey_name=str(r.get("騎手","") or "").strip()
            trainer_name="" if trainer_name in {"nan","None","<NA>","0"} else trainer_name
            jockey_name="" if jockey_name in {"nan","None","<NA>","0"} else jockey_name

            training_reason=any(
                z in reasons
                for z in ["高勝率A3","通常A3","調教師◎","調教コース◎","B3"]
            )
            person_parts=[]
            if training_reason and trainer_name:
                person_parts.append(f"調教師 {trainer_name}")
            if jockey_name:
                person_parts.append(f"騎手 {jockey_name}")
            people=f"<span class='small'>{' ｜ '.join(person_parts)}</span><br>" if person_parts else ""

            horse_html.append(
                f"<div style='padding:8px 0;border-top:1px solid rgba(127,215,245,.18)'>"
                f"<span class='crown-mark'>{crown_mark}</span>"
                f"<span style='font-size:18px;font-weight:900'>{int(r['馬番'])} {r['馬名']}</span> "
                f"<span class='small'>単勝 {odds_text}</span><br>"
                f"{people}{crown_tags}{tags}</div>"
            )
        st.markdown(
            f"<div class='pick pick-hot'><b>{place}{rno}R {card['race_name']}</b> "
            f"<span class='small'>{card['surface']}{card['distance']}m｜{len(card['horses'])}頭該当</span>"
            + "".join(horse_html) + "</div>",
            unsafe_allow_html=True
        )

st.caption("※ TODAY’S NEXUS PICKは閲覧フィルターではありません。注目馬がいないレースも下の全レース選択から必ず開けます。")
st.divider()

# ---------------------------------------------------------
# 2. ALL RACE SELECTOR
# ---------------------------------------------------------
st.markdown("## 全レース選択")
d,venue,race_no,current=race_selector(df,"main_race")
if current.empty:
    st.warning("レースデータがありません。")
    st.stop()

race_name=str(current["レース名"].iloc[0])
surface=str(current["芝・ダ"].iloc[0]).strip()
distance=int(pd.to_numeric(current["距離"],errors="coerce").iloc[0])
race_key=f"{d}_{venue}_{race_no}"

# ---------------------------------------------------------
# 3. RACE INFO + TRACK
# ---------------------------------------------------------
st.markdown(f"## {venue}{race_no}R {race_name}")
st.markdown(f"**{surface}{distance}m** ｜ {len(current)}頭")

now=datetime.now(ZoneInfo("Asia/Tokyo"))
today=int(now.strftime("%Y%m%d"))
yesterday=int((now-timedelta(days=1)).strftime("%Y%m%d"))

valid_dates=pd.to_numeric(df["年月日"],errors="coerce")
valid_dates=valid_dates[(valid_dates>=20000101)&(valid_dates<=20991231)]
latest_loaded_date=int(valid_dates.max()) if not valid_dates.empty else int(d)

# 0:00〜7:59は、最新取込日が前日なら前開催日のJRA情報を自動参照する。
rollover_previous_day=(
    now.hour < 8
    and int(d)==yesterday
    and int(d)==latest_loaded_date
)
is_live=(int(d)==today or rollover_previous_day)

official={}; jra_errors=[]
if is_live:
    rc1,rc2=st.columns([1,4],vertical_alignment="center")
    with rc1:
        if st.button("🔄 JRA再取得",use_container_width=True,key=f"jra_refresh_{race_key}"):
            fetch_jra_track_conditions.clear()
            for k in [
                f"going_init_{race_key}",
                f"cush_init_{race_key}",
                f"moist_init_{race_key}",
                f"weather_init_{race_key}",
            ]:
                st.session_state.pop(k,None)
            st.rerun()
    with rc2:
        if rollover_previous_day:
            st.caption("JRA公式馬場情報を自動取得（早朝の前開催日ロールオーバー）。")
        else:
            st.caption("JRA公式馬場情報を自動取得。")

    with st.spinner("JRA馬場情報取得中..."):
        cond,jra_errors=fetch_jra_track_conditions()
        official=cond.get(venue,{})
else:
    st.caption("過去日レースのためJRA現在値は自動適用しません。")

if official:
    op=[]
    if official.get("turf_going"): op.append(f'芝 {official["turf_going"]}')
    if official.get("cushion") is not None: op.append(f'Cushion {float(official["cushion"]):.1f}')
    if official.get("dirt_going"): op.append(f'ダ {official["dirt_going"]}')
    if official.get("dirt_moisture") is not None: op.append(f'ダ含水率 {float(official["dirt_moisture"]):.1f}%')
    if official.get("weather"): op.append(f'天候 {official["weather"]}')
    st.success("JRA公式 ｜ "+" / ".join(op))
elif is_live:
    st.warning("JRA公式値を取得できませんでした。手動入力で分析できます。")
    if jra_errors:
        with st.expander("JRA自動取得エラー",expanded=False):
            for err in jra_errors[-8:]:
                st.code(err)

st.markdown("### 馬場情報")
going_opts=["良","稍重","重","不良"]

if surface=="芝":
    official_going=official.get("turf_going") if official else None
    official_cush=official.get("cushion") if official else None
    official_weather=official.get("weather") if official else None

    going_key=f"going_{race_key}"
    if not st.session_state.get(f"going_init_{race_key}",False):
        st.session_state[going_key]=official_going if official_going in going_opts else "良"
        st.session_state[f"going_init_{race_key}"]=True

    cush_key=f"cush_{race_key}"
    if not st.session_state.get(f"cush_init_{race_key}",False):
        st.session_state[cush_key]=f"{float(official_cush):.1f}" if official_cush is not None else ""
        st.session_state[f"cush_init_{race_key}"]=True

    weather_key=f"weather_{race_key}"
    if not st.session_state.get(f"weather_init_{race_key}",False):
        st.session_state[weather_key]=str(official_weather or "晴")
        st.session_state[f"weather_init_{race_key}"]=True

    c1,c2,c3=st.columns(3)
    going=c1.selectbox("馬場状態",going_opts,key=going_key)
    cushion_text=c2.text_input("クッション値",key=cush_key,placeholder="未取得なら手動入力")
    weather=c3.text_input("天候",key=weather_key)

    try:
        cushion=float(cushion_text) if str(cushion_text).strip() else None
    except ValueError:
        cushion=None
        c2.warning("クッション値は数値で入力してください。")
    moisture=None

else:
    official_going=official.get("dirt_going") if official else None
    official_moisture=official.get("dirt_moisture") if official else None
    official_weather=official.get("weather") if official else None

    going_key=f"going_{race_key}"
    if not st.session_state.get(f"going_init_{race_key}",False):
        st.session_state[going_key]=official_going if official_going in going_opts else "良"
        st.session_state[f"going_init_{race_key}"]=True

    moist_key=f"moist_{race_key}"
    if not st.session_state.get(f"moist_init_{race_key}",False):
        st.session_state[moist_key]=f"{float(official_moisture):.1f}" if official_moisture is not None else ""
        st.session_state[f"moist_init_{race_key}"]=True

    weather_key=f"weather_{race_key}"
    if not st.session_state.get(f"weather_init_{race_key}",False):
        st.session_state[weather_key]=str(official_weather or "晴")
        st.session_state[f"weather_init_{race_key}"]=True

    c1,c2,c3=st.columns(3)
    going=c1.selectbox("馬場状態",going_opts,key=going_key)
    moisture_text=c2.text_input("含水率",key=moist_key,placeholder="未取得なら手動入力（例 5.8）")
    weather=c3.text_input("天候",key=weather_key)

    try:
        moisture=float(moisture_text) if str(moisture_text).strip() else None
    except ValueError:
        moisture=None
        c2.warning("含水率は数値で入力してください。")
    cushion=None

# M auto-generation / unresolved queue
m_status,m_queue,m_generated=ensure_current_horses(current)
get_m.clear()
mb=get_m(dataset_signature()+"|generated")
if not m_generated.empty:
    base_runner=mb.get("runner",pd.DataFrame())
    mb["runner"]=pd.concat([base_runner,m_generated],ignore_index=True,sort=False).drop_duplicates("血統登録番号",keep="last")
m_eval=evaluate_m(current,venue,distance,surface,going=going,cushion=cushion,moisture=moisture,bundle=mb)
m_eval=m_eval.merge(m_status[["馬番","M付与状態","M自動生成","M補完待ち"]],on="馬番",how="left")
m_eval["M表示"]=np.where(m_eval["M補完待ち"].fillna(False),"未",m_eval["M評価"].fillna("－"))
cur=current.merge(m_eval,on="馬番",how="left")
cur=add_crown_flags(cur)

# ---------------------------------------------------------
# 4. MAIN STARTING TABLE (pre-analysis)
# ---------------------------------------------------------
st.markdown("### 出馬表")
pre=cur.copy()
pre["調教"]=pre.apply(training_mark,axis=1)
pre["M血統"]=pre["M表示"].fillna("－")
pre["展開"]="－"
pre["勝率"]="－"
pre["単勝"]="－"
pre["王冠"]=pre["crown_mark"].fillna("")
precols=[c for c in ["馬番","馬名","王冠","騎手","調教師","所属","調教","M血統","展開","勝率","単勝"] if c in pre.columns]
st.dataframe(pre[precols],use_container_width=True,hide_index=True)
st.caption("M血統：◎=正式採用級のプラス条件（現馬場で強い逆風があれば○へ） / ○=プラス適性 / △=中立・保留 / ×=再現性あるマイナス / －=今回参照条件なし / 未=M未付与")

# ---------------------------------------------------------
# 5. ANALYZE / AUTO-MANUAL SIMULATOR
# ---------------------------------------------------------
st.markdown("### Race Simulator")
mode=st.segmented_control("展開モード",["AUTO","MANUAL"],default="AUTO",key=f"sim_mode_{race_key}")
manual_scenario=None; manual_leaders=[]; manual_positions={}
if mode=="MANUAL":
    manual_scenario=st.selectbox("想定ペース",["S","M","H","上がり勝負","ロンスパ"],index=1,key=f"pace_{race_key}")
    horse_opts={f"{int(r['馬番'])} {r['馬名']}":int(r["馬番"]) for _,r in cur.iterrows()}
    leader_labels=st.multiselect("逃げ馬（追加・削除・指定）",list(horse_opts),key=f"leaders_{race_key}")
    manual_leaders=[horse_opts[z] for z in leader_labels]
    with st.expander("各馬の想定位置を修正",expanded=False):
        for _,r in cur.iterrows():
            no=int(r["馬番"])
            val=st.selectbox(f"{no} {r['馬名']}",["AUTO","逃げ","先行","中団","後方"],
                             key=f"pos_{race_key}_{no}")
            if val!="AUTO": manual_positions[no]=val

run_label="再シミュレーション" if mode=="MANUAL" else "Nexus分析を実行"
if st.button(f"▶ {run_label}",type="primary",use_container_width=True,key=f"run_{race_key}"):
    with st.spinner("Race Simulator / Nexus計算中..."):
        hist,rd_course,thresholds=get_rd(dataset_signature())
        rd,raceinfo,scenario=run_race_development(
            cur,hist,rd_course,thresholds,n_sims=10000,route_bias="フラット",
            manual_scenario=manual_scenario if mode=="MANUAL" else None,
            manual_leaders=manual_leaders if mode=="MANUAL" else None,
            manual_positions=manual_positions if mode=="MANUAL" else None,
        )
        turf,dirt,ped_course=get_pedigree()
        ped=evaluate_pedigree_core(cur,turf,dirt,ped_course)
        merged=cur.merge(ped,on="馬番",how="left").merge(rd,on=["馬番","馬名"],how="left")
        merged=attach_m_signature(merged,mb)
        merged=add_distance_m(merged,mb)
        nexus=calculate_base_scores(merged)
        st.session_state[f"nexus_{race_key}"]=nexus
        st.session_state[f"raceinfo_{race_key}"]=raceinfo
        st.session_state[f"scenario_{race_key}"]=scenario
        st.session_state[f"simstate_{race_key}"]=mode

if st.button("自動予測に戻す",use_container_width=False,key=f"reset_auto_{race_key}"):
    st.session_state[f"sim_mode_{race_key}"]="AUTO"
    st.rerun()

nexus=st.session_state.get(f"nexus_{race_key}")
if nexus is None:
    st.info("Nexus分析を実行すると、勝率・相手・隊列・FINAL NEXUSを表示します。")
    st.stop()

raceinfo=st.session_state.get(f"raceinfo_{race_key}",{})
scenario=st.session_state.get(f"scenario_{race_key}",{})
simstate=st.session_state.get(f"simstate_{race_key}","AUTO")

m1,m2,m3,m4=st.columns(4)
m1.metric("展開",simstate)
m2.metric("想定ペース",scenario_jp(scenario.get("PredictedScenario","-")))
m3.metric("LeadPressure",raceinfo.get("先行圧力","-"))
m4.metric("LeadCompetition",f"{float(raceinfo.get('LeadCompetitionIndex_v2',0)):.3f}")

# ---------------------------------------------------------
# Surface / Day Bias
# ---------------------------------------------------------
st.markdown("### 当日Bias")

hist,_,_=get_rd(dataset_signature())
auto_bias=estimate_same_day_bias(hist,d,venue,surface,race_no)

bias_mode=st.segmented_control(
    "Biasモード",
    ["AUTO (Past-Only)","手動"],
    default="AUTO (Past-Only)",
    key=f"bias_mode_{race_key}",
)

fb_map={
    "前有利":1.0,
    "やや前有利":0.5,
    "フラット":0.0,
    "やや差し有利":-0.5,
    "差し有利":-1.0,
}
io_map={
    "内有利":1.0,
    "やや内有利":0.5,
    "フラット":0.0,
    "やや外有利":-0.5,
    "外有利":-1.0,
}

if bias_mode=="AUTO (Past-Only)":
    fb_bias=float(auto_bias.get("front_back_bias",0.0) or 0.0)
    io_bias=float(auto_bias.get("inside_outside_bias",0.0) or 0.0)

    b1,b2,b3=st.columns(3)
    b1.metric("前後Bias",str(auto_bias.get("label_fb","フラット")),f"{fb_bias:+.2f}")
    b2.metric("内外Bias",str(auto_bias.get("label_io","フラット")),f"{io_bias:+.2f}")
    b3.metric("参照済みレース",f"{int(auto_bias.get('sample_races',0) or 0)}R")

    st.caption("AUTOは同日・同競馬場・同芝ダートの当該レース以前の結果だけで推定します。")
else:
    b1,b2=st.columns(2)

    auto_fb_label=str(auto_bias.get("label_fb","フラット"))
    auto_io_label=str(auto_bias.get("label_io","フラット"))
    if auto_fb_label not in fb_map:
        auto_fb_label="フラット"
    if auto_io_label not in io_map:
        auto_io_label="フラット"

    fb_labels=list(fb_map.keys())
    io_labels=list(io_map.keys())

    fb_label=b1.selectbox(
        "前後Bias手動",
        fb_labels,
        index=fb_labels.index(auto_fb_label),
        key=f"fb_manual_{race_key}",
    )
    io_label=b2.selectbox(
        "内外Bias手動",
        io_labels,
        index=io_labels.index(auto_io_label),
        key=f"io_manual_{race_key}",
    )

    fb_bias=fb_map[fb_label]
    io_bias=io_map[io_label]

    st.caption(
        f"AUTO参考値：前後 {auto_fb_label} / 内外 {auto_io_label} "
        f"（参照 {int(auto_bias.get('sample_races',0) or 0)}R）"
    )

with_bias=add_bias_fit(nexus,fb_bias,io_bias)
final=apply_surface_adjustment(
    with_bias,
    surface=surface,
    going=going,
    cushion_band=cushion_to_nexus_band(cushion) if surface=="芝" and cushion is not None else None,
    front_back_fit_col="front_back_fit",
    inside_outside_fit_col="inside_outside_fit",
)
final=final.merge(m_eval[["馬番","M評価","M表示","M付与状態","M補完待ち","M×コース","M_STRICT_110","M_STRICT_REASON"]],on="馬番",how="left",suffixes=("","_m"))

# ---------------------------------------------------------
# 6. ODDS + PROBABILITY / VALUE
# ---------------------------------------------------------
st.markdown("### 勝率計算")

# IMPORTANT:
# オッズ保存用session_stateと更新ボタンのkeyを完全分離する。
# 旧版では同一keyを使っていたため、buttonのbool値がodds辞書を上書きして
# AttributeError: 'bool' object has no attribute 'get' が発生していた。
odds_key=f"odds_data_{race_key}"
odds_refresh_key=f"odds_refresh_{race_key}"

refresh=st.button(
    "🔄 単勝オッズ取得 / 更新",
    use_container_width=True,
    key=odds_refresh_key,
)

cached_odds=st.session_state.get(odds_key,{})
if not isinstance(cached_odds,dict):
    cached_odds={}
    st.session_state[odds_key]={}

if refresh or not cached_odds:
    horses=[
        {"horse_no":int(r["馬番"]),"horse_name":str(r["馬名"])}
        for _,r in current.iterrows()
        if pd.notna(r.get("馬番"))
    ]
    data,errs=fetch_win_odds(
        d,venue,race_no,horses,
        force_update=refresh
    )
    st.session_state[odds_key]=data if isinstance(data,dict) else {}
    st.session_state[f"odds_err_{race_key}"]=errs
    cached_odds=st.session_state[odds_key]

odds_data=cached_odds if isinstance(cached_odds,dict) else {}

def _odds_item(horse_no):
    if pd.isna(horse_no):
        return {}
    item=odds_data.get(int(horse_no),{})
    return item if isinstance(item,dict) else {}

val=final.copy()
val["単勝オッズ"]=val["馬番"].map(lambda n:_odds_item(n).get("odds"))
val["人気"]=val["馬番"].map(lambda n:_odds_item(n).get("popularity"))
val=add_value_metrics(val,odds_col="単勝オッズ",prob_col="final_nexus_prob")
val["推定勝率"]=(pd.to_numeric(val["final_nexus_prob"],errors="coerce")*100).round(1)
val["市場期待"]= (expected_market(val["単勝オッズ"])*100).round(1)
val["差pt"]=(val["推定勝率"]-val["市場期待"]).round(1)
if "MC複勝率" in val.columns:
    val["複勝圏確率"]=(pd.to_numeric(val["MC複勝率"],errors="coerce")*100).round(1)
else:
    val["複勝圏確率"]=np.nan

probcols=[c for c in ["馬番","馬名","推定勝率","複勝圏確率","市場期待","差pt","単勝オッズ","VALUE"] if c in val.columns]
st.dataframe(val[probcols].sort_values("推定勝率",ascending=False),use_container_width=True,hide_index=True)

# ---------------------------------------------------------
# 7. MAIN TABLE UPDATED
# ---------------------------------------------------------
st.markdown("### 新・出馬表")
main=val.copy()
main["調教"]=main.apply(training_mark,axis=1)
main["M血統"]=main["M表示"].fillna("－")
main["展開"]=main["展開評価"].fillna("－")
main["勝率"]=main["推定勝率"].map(lambda z:f"{z:.1f}%" if pd.notna(z) else "－")
main["単勝"]=pd.to_numeric(main["単勝オッズ"],errors="coerce").map(lambda z:f"{z:.1f}" if pd.notna(z) else "－")
main["王冠"]=main["crown_mark"].fillna("")
main_cols=[c for c in ["馬番","馬名","王冠","騎手","調教師","所属","調教","M血統","展開","勝率","単勝"] if c in main.columns]
st.dataframe(main[main_cols],use_container_width=True,hide_index=True)

# ---------------------------------------------------------
# 8. RECOMMENDED PARTNERS
# ---------------------------------------------------------
st.markdown("### 推奨の相手")
anchors=anchor_candidates(val)
anchor_labels=[]; amap={}
for _,r in anchors.iterrows():
    no=int(r["馬番"])
    lab=f"{no} {r['馬名']} {'◎候補' if bool(r.get('partner_anchor_eligible',False)) else ''}"
    anchor_labels.append(lab); amap[lab]=no
anchor_label=st.selectbox("本命・注目馬",anchor_labels,key=f"anchor_{race_key}")
anchor_no=amap[anchor_label]
partners=rank_partners(val,anchor_no,exclude_jirai=True)
recs=build_partner_recommendations(val,partners,anchor_no,odds_data,max_total=5)
if recs.empty:
    st.info("相手候補がありません。")
else:
    for _,r in recs.iterrows():
        pop=f"{int(r['人気'])}人気" if pd.notna(r["人気"]) else "人気不明"
        odds=f"{float(r['単勝オッズ']):.1f}倍" if pd.notna(r["単勝オッズ"]) else "オッズ未取得"
        st.markdown(
            f"<div class='pick'><b>{int(r['馬番'])} {r['馬名']}</b> "
            f"<span class='tag'>{r['区分']}</span><br>{r['理由']}<br>"
            f"<span class='small'>{pop} / {odds}</span></div>",unsafe_allow_html=True
        )

# ---------------------------------------------------------
# 9. ROUTE / SIMULATOR DETAILS
# ---------------------------------------------------------
st.markdown("### 隊列予想図")
st.caption("1コーナーと最終コーナーを必ず表示。MANUAL変更後は再シミュレーション結果を表示します。")
route=val.copy()
needed={"PredFirstRank","Pred4ScenarioRank","初角ゾーン","最終角ゾーン","初角進路","最終角進路"}
if needed.issubset(route.columns):
    st.markdown(render_route_grid(route,"初角","Nexus"),unsafe_allow_html=True)
    st.markdown(render_route_grid(route,"最終","Nexus"),unsafe_allow_html=True)
else:
    st.info("隊列表示列が不足しています。再シミュレーションしてください。")

# ---------------------------------------------------------
# 10. FINAL NEXUS TOP3
# ---------------------------------------------------------
st.markdown("### FINAL NEXUS TOP3")
top3=val.sort_values(["final_nexus_prob","VALUE"],ascending=False,na_position="last").head(3)
cols=st.columns(len(top3))
for col,(_,r) in zip(cols,top3.iterrows()):
    with col:
        st.metric(f"{int(r['馬番'])} {r['馬名']}",f"{float(r['推定勝率']):.1f}%")
        tags=[]
        if int(r.get("crown_count",0) or 0)>0:
            tags.append(str(r.get("crown_mark","👑")))
        if training_mark(r)=="◎": tags.append("調教◎")
        if str(r.get("M評価",""))=="◎": tags.append("M◎")
        if str(r.get("展開評価",""))=="◎": tags.append("展開◎")
        if pd.notna(r.get("VALUE")): tags.append(f"VALUE {float(r['VALUE']):.2f}")
        st.caption(" / ".join(tags) if tags else "Nexus総合上位")

# ---------------------------------------------------------
# 11. DETAILS / COLLAPSIBLE
# ---------------------------------------------------------
st.markdown("### 詳細分析")
with st.expander("👑 クラウンルール該当詳細",expanded=False):
    crown_view=cur.copy()
    crown_view=crown_view[pd.to_numeric(crown_view.get("crown_count",0),errors="coerce").fillna(0)>0]
    if crown_view.empty:
        st.info("このレースにクラウンルール該当馬はいません。")
    else:
        show=crown_view[[c for c in ["馬番","馬名","crown_mark","crown_count","crown_reasons"] if c in crown_view.columns]].rename(columns={
            "crown_mark":"王冠","crown_count":"該当数","crown_reasons":"王冠理由",
        })
        st.dataframe(show,use_container_width=True,hide_index=True)

with st.expander("調教詳細",expanded=False):
    td=current.copy()
    td["通常A3"]=td.apply(lambda r:"○" if training_flags(r)["通常A3"] else "－",axis=1)
    td["高勝率A3"]=td.apply(lambda r:"○" if training_flags(r)["高勝率A3"] else "－",axis=1)
    td["調教師判定表示"]=td.apply(lambda r:"○" if training_flags(r)["調教師判定"] else "－",axis=1)
    td["B3表示"]=td.apply(lambda r:"○" if training_flags(r)["B3"] else "－",axis=1)
    td["調教コース表示"]=td.apply(lambda r:"○" if training_flags(r)["調教コース"] else "－",axis=1)
    td["地雷表示"]=td.apply(lambda r:"×" if training_flags(r)["地雷"] else "－",axis=1)
    td["調教表示"]=td.apply(detail_training,axis=1)
    st.dataframe(td[["馬番","馬名","通常A3","高勝率A3","調教師判定表示","B3表示","調教コース表示","地雷表示","調教表示"]],use_container_width=True,hide_index=True)

with st.expander("調教判定データ監査",expanded=False):
    audit_cols=["A3LAP判定","A3高勝率Lap","調教師判定","B3LAP判定","コース判定","地雷ラップ判定"]
    missing=[c for c in audit_cols if c not in current.columns]
    if missing: st.error("調教元データに不足列があります: "+", ".join(missing))
    else:
        st.success("通常A3と高勝率A3を別列として認識しています。")
        st.dataframe(current[["馬番","馬名"]+audit_cols],use_container_width=True,hide_index=True)

with st.expander("M血統未付与管理 / 自動補完",expanded=False):
    st.caption("M未付与馬は減点せず『未』表示。父・母父・母母父の3種牡馬がM種牡馬マスタに揃えば自動生成します。")
    st.dataframe(m_status[["馬番","馬名","M付与状態","M自動生成","M補完待ち"]],use_container_width=True,hide_index=True)
    if not m_queue.empty:
        st.warning(f"補完待ち {len(m_queue)}頭")
        st.dataframe(m_queue[["馬名","父","母父","母母父","不足項目","状態"]],use_container_width=True,hide_index=True)
    else:
        st.success("このレースにM補完待ちはありません。")

with st.expander("M血統詳細",expanded=False):
    md=m_eval.copy()
    st.dataframe(md[[c for c in ["馬番","M付与状態","M表示","M評価","M9","M×コース","M×馬場状態","M物理帯","M×クッション値","M×含水率","M×馬場物理複合","Mプラス根拠","Mマイナス根拠","M評価根拠","M×距離","M×坂","M×芝ダ"] if c in md.columns]],
                 use_container_width=True,hide_index=True)

with st.expander("Simulator内部値",expanded=False):
    scols=[c for c in ["馬番","馬名","今回想定脚質","LeadProb_Jockey","LeadPressure","PredFirstRank","Pred3Rank",
                       "Pred4ScenarioRank","MC逃げ率","MC平均4角順位","PositionValue","展開評価"] if c in val.columns]
    st.dataframe(val[scols],use_container_width=True,hide_index=True)

with st.expander("勝率計算詳細",expanded=False):
    st.dataframe(val[probcols+[c for c in ["Nexus適正オッズ","VALUE判定"] if c in val.columns]],use_container_width=True,hide_index=True)

with st.expander("推奨相手の算出根拠",expanded=False):
    st.dataframe(partners,use_container_width=True,hide_index=True)

st.caption("M血統・調教・展開はUI上で分離表示。M◎だから勝率へ固定加点する設計にはしていません。")
