from pathlib import Path
import streamlit as st
import pandas as pd

from modules.training_radar import load_training, summarize_races, race_horses
from modules.pedigree_core import load_masters, evaluate_pedigree_core
from modules.partner_compatibility import anchor_candidates, rank_partners
from modules.race_development_core import load_rd_data, run_race_development
from modules.nexus_probability import calculate_base_scores, apply_surface_adjustment
from modules.day_bias import estimate_same_day_bias, add_bias_fit
from modules.odds import fetch_win_odds
from modules.value import add_value_metrics

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "training_current.csv"

st.set_page_config(page_title="Runaway's Nexus", page_icon="🏇", layout="wide")

st.markdown("""
<style>
.stApp {background:#061525;color:#eef6ff}
[data-testid='stSidebar'] {background:#081c30}
.nexus-title {font-size:34px;font-weight:800;letter-spacing:.3px;color:#f5fbff;margin-bottom:0}
.nexus-sub {color:#7fd7f5;margin-top:0}
.race-card {border:1px solid #1f7ea5;border-radius:12px;padding:14px 16px;margin:8px 0;background:#08233a}
.star {color:#ffb347;font-weight:800;font-size:22px}
.badge {display:inline-block;padding:3px 8px;margin-right:6px;border-radius:8px;background:#0d3a4e;border:1px solid #2e95b8;font-size:12px}
.badge-green {background:#103c32;border-color:#3ab67f}
.badge-pink {background:#40203e;border-color:#c05ab3}
.badge-warn {background:#3d2d10;border-color:#d99f34}
.metric-card {border:1px solid #1f7ea5;border-radius:12px;padding:10px;background:#08233a}
[data-testid='stMetric'] {background:#08233a;border:1px solid #1f7ea5;border-radius:12px;padding:10px}
div.stButton > button {border:1px solid #2e95b8;border-radius:10px;background:#0b2941;color:#f5fbff;font-weight:700}
div.stButton > button:hover {border-color:#7fd7f5;background:#123953;color:#ffffff}
hr {border-color:#153d56}
</style>
""", unsafe_allow_html=True)

st.markdown("<p class='nexus-title'>Runaway’s Nexus</p><p class='nexus-sub'>Training × Pedigree × Development × Track Condition</p>", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def get_training():
    return load_training(DATA)

@st.cache_data(show_spinner="血統マスタ読込中...")
def get_pedigree_masters():
    return load_masters()

@st.cache_data(show_spinner="Race Development履歴読込中...")
def get_rd_data():
    return load_rd_data()


def _race_selector(df, key_prefix="race"):
    dates = sorted([int(x) for x in df["年月日"].dropna().unique()], reverse=True)
    desired_date = st.session_state.pop("radar_target_date", None)
    date_index = dates.index(int(desired_date)) if desired_date is not None and int(desired_date) in dates else 0
    d = st.selectbox("開催日", dates, index=date_index, key=f"{key_prefix}_date")

    day_df = df[df["年月日"] == d]
    venues = sorted(day_df["場所"].dropna().astype(str).unique().tolist())
    desired_venue = st.session_state.pop("radar_target_venue", None)
    venue_index = venues.index(str(desired_venue)) if desired_venue is not None and str(desired_venue) in venues else 0
    venue = st.selectbox("開催場", venues, index=venue_index, key=f"{key_prefix}_venue")

    vdf = day_df[day_df["場所"] == venue]
    race_nos = sorted([int(x) for x in vdf["R"].dropna().unique()])
    desired_race = st.session_state.pop("radar_target_race", None)
    race_index = race_nos.index(int(desired_race)) if desired_race is not None and int(desired_race) in race_nos else 0
    race_no = st.selectbox("レース", race_nos, index=race_index, key=f"{key_prefix}_r")
    current = vdf[vdf["R"] == race_no].copy().sort_values("馬番")
    return d, venue, race_no, current


def _jump_to_race(date_value, venue_value, race_value):
    st.session_state["radar_target_date"] = int(date_value)
    st.session_state["radar_target_venue"] = str(venue_value)
    st.session_state["radar_target_race"] = int(race_value)
    st.session_state["nexus_page"] = "🏁 Race Analysis"


def _nexus_tag(row: pd.Series) -> str:
    stars = int(pd.to_numeric(row.get("training_stars", 0), errors="coerce") or 0)
    ped = str(row.get("pedigree_core_grade", ""))
    dev = str(row.get("展開評価", ""))
    if stars >= 2 and ped == "◎" and dev == "◎":
        return "🔥🧬🏁 NEXUS特注"
    if stars >= 2 and dev == "◎":
        return "🔥🏁 NEXUS注目"
    if stars >= 2 and ped == "◎":
        return "🔥🧬 調教×血統"
    if ped == "◎" and dev == "◎":
        return "🧬🏁 血統×展開"
    return ""


def _race_attention_label(max_stars: int, elite_count: int, strong_count: int) -> str:
    if int(elite_count or 0) > 0 or int(max_stars or 0) >= 3:
        return "🔥 最優先"
    if int(strong_count or 0) > 0:
        return "注目"
    return "チェック"


df = get_training()
races = summarize_races(df)

NAV_PAGES = ["🏠 Training Radar", "🏁 Race Analysis", "🌱 Track Condition", "⚙️ Settings"]
if "nexus_page" not in st.session_state:
    st.session_state["nexus_page"] = NAV_PAGES[0]
page = st.sidebar.radio("NAVIGATION", NAV_PAGES, key="nexus_page")

if page == "🏠 Training Radar":
    st.subheader("TODAY'S TRAINING RADAR")
    dates = sorted([int(x) for x in df["年月日"].dropna().unique()], reverse=True)
    selected_date = st.selectbox("開催日", dates, index=0)
    day = races[races["年月日"] == selected_date].copy()
    venues = ["全場"] + sorted(day["場所"].dropna().astype(str).unique().tolist())
    venue = st.segmented_control("開催場", venues, default="全場")
    if venue != "全場":
        day = day[day["場所"] == venue]

    focus = day[day["max_stars"] > 0]
    if focus.empty:
        st.info("この開催日の主調教★レースはありません。")
    for idx, r in focus.iterrows():
        badges = [f"<span class='badge badge-green'>好調教 {int(r.good_training_count)}頭</span>"]
        if r.strong_training_count:
            badges.append(f"<span class='badge badge-pink'>強判定 {int(r.strong_training_count)}頭</span>")
        if r.course_count:
            badges.append(f"<span class='badge'>Course {int(r.course_count)}</span>")
        if r.b3_count:
            badges.append(f"<span class='badge'>B3 {int(r.b3_count)}</span>")
        if r.jirai_count:
            badges.append(f"<span class='badge badge-warn'>☠ {int(r.jirai_count)}</span>")
        c_main, c_open = st.columns([8, 1.4])
        with c_main:
            attention = _race_attention_label(r.max_stars, r.elite_count, r.strong_training_count)
            st.markdown(
                f"<div class='race-card'><b>{r['場所']} {int(r['R'])}R</b>　{r['レース名']}　"
                f"<span class='star'>{r['stars']}</span>　<span class='badge badge-pink'>{attention}</span><br>" + "".join(badges) + "</div>",
                unsafe_allow_html=True,
            )
        with c_open:
            st.write("")
            st.button(
                "開く →",
                key=f"open_race_{selected_date}_{r['場所']}_{int(r['R'])}",
                use_container_width=True,
                on_click=_jump_to_race,
                args=(selected_date, r["場所"], int(r["R"])),
            )
    st.divider()
    st.caption("★=通常A3 / ★★=高勝率A3または調教師判定 / ★★★=強判定の重複。Course・B3は補助バッジで★には加算しません。")

elif page == "🏁 Race Analysis":
    st.subheader("RACE ANALYSIS")
    d, venue, race_no, current = _race_selector(df, "analysis")
    if current.empty:
        st.warning("レースデータがありません。")
        st.stop()

    race_name = str(current["レース名"].iloc[0])
    surface = str(current["芝・ダ"].iloc[0]).strip()
    distance = int(pd.to_numeric(current["距離"], errors="coerce").iloc[0])
    st.caption(f"{d} {venue} {race_no}R {race_name} ｜ {surface}{distance}m ｜ {len(current)}頭")

    # Training is always available before heavy prediction.
    view = current.copy()
    view["調教★"] = view["training_stars"].map(lambda n: "★" * int(n) if n else "-")
    view["Course"] = view["course_badge"].map(lambda x: "C" if x else "-")
    view["B3"] = view["b3_badge"].map(lambda x: "B3" if x else "-")
    view["地雷"] = view["jirai_badge"].map(lambda x: "☠" if x else "-")

    st.markdown("#### ① Training")
    show = [c for c in ["馬番","馬名","父","調教師","調教★","training_level","Course","B3","地雷","ZI"] if c in view.columns]
    st.dataframe(view[show], use_container_width=True, hide_index=True)

    st.markdown("#### ② Pedigree Core")
    turf, dirt, course = get_pedigree_masters()
    ped = evaluate_pedigree_core(current, turf, dirt, course)
    ped_show = current[["馬番","馬名","父"]].merge(ped, on="馬番", how="left")
    st.dataframe(
        ped_show[["馬番","馬名","父","ped_distance_grade","ped_turn_grade","ped_slope_grade","pedigree_core_grade","pedigree_core_score"]]
        .rename(columns={"ped_distance_grade":"距離区分","ped_turn_grade":"左右","ped_slope_grade":"坂","pedigree_core_grade":"血統Core","pedigree_core_score":"Core指数"}),
        use_container_width=True, hide_index=True,
    )

    st.markdown("#### ③ Race Development → Nexus Base")
    st.caption("正式Race Developmentモデル＋10,000回Monte Carloを実行し、MC勝率をNexusの基礎勝率として使用します。")
    if st.button("▶ Nexus分析を実行", type="primary", use_container_width=True):
        with st.spinner("Race Development正式モデル・Monte Carlo・Nexus Baseを計算中..."):
            hist, rd_course, thresholds = get_rd_data()
            rd, raceinfo, scenario = run_race_development(current, hist, rd_course, thresholds, n_sims=10000, route_bias="フラット")
            merged = current.merge(ped, on="馬番", how="left").merge(rd, on=["馬番","馬名"], how="left")
            nexus = calculate_base_scores(merged)
            st.session_state["nexus_result"] = nexus
            st.session_state["nexus_race_key"] = f"{d}_{venue}_{race_no}"
            st.session_state["nexus_raceinfo"] = raceinfo
            st.session_state["nexus_scenario"] = scenario

    race_key = f"{d}_{venue}_{race_no}"
    if st.session_state.get("nexus_race_key") == race_key and "nexus_result" in st.session_state:
        nexus = st.session_state["nexus_result"].copy()
        ri = st.session_state.get("nexus_raceinfo", {})
        sc = st.session_state.get("nexus_scenario", {})
        m = st.columns(4)
        m[0].metric("先行圧力", ri.get("先行圧力", "-"))
        m[1].metric("展開シナリオ", sc.get("PredictedScenario", "-"))
        m[2].metric("LeadCompetition", f"{ri.get('LeadCompetitionIndex_v2',0):.3f}")
        m[3].metric("MC勝率合計", f"{nexus['race_development_prob'].sum()*100:.1f}%")

        result = nexus.copy()
        result["RD勝率"] = (pd.to_numeric(result["race_development_prob"], errors="coerce") * 100).round(1)
        result["Nexus Base"] = (pd.to_numeric(result["nexus_base_prob"], errors="coerce") * 100).round(1)
        result["Δ"] = ((result["nexus_base_prob"] - result["race_development_prob"]) * 100).round(1)
        result["調教★"] = result["training_stars"].map(lambda n: "★" * int(n) if n else "-")
        result["NEXUS判定"] = result.apply(_nexus_tag, axis=1)
        out_cols = [c for c in ["馬番","馬名","調教★","pedigree_core_grade","展開評価","今回想定脚質","RD勝率","Nexus Base","Δ","NEXUS判定"] if c in result.columns]
        st.dataframe(result[out_cols].sort_values("Nexus Base", ascending=False), use_container_width=True, hide_index=True)

        tagged = result[result["NEXUS判定"] != ""].sort_values("Nexus Base", ascending=False)
        if not tagged.empty:
            st.markdown("##### NEXUS PICKS")
            for _, hr in tagged.head(5).iterrows():
                st.markdown(
                    f"<div class='race-card'><b>{int(hr['馬番'])}番 {hr['馬名']}</b>　{hr['NEXUS判定']}<br>"
                    f"<span class='badge'>調教 {hr['調教★']}</span>"
                    f"<span class='badge'>血統 {hr.get('pedigree_core_grade','-')}</span>"
                    f"<span class='badge'>展開 {hr.get('展開評価','-')}</span>"
                    f"<span class='badge badge-green'>Nexus Base {hr['Nexus Base']:.1f}%</span></div>",
                    unsafe_allow_html=True,
                )

        st.markdown("#### ④ 当日Surface / Day Bias")
        c1, c2 = st.columns(2)
        going = c1.selectbox("馬場状態", ["未指定","良","稍重","重","不良"], key=f"surface_going_{race_key}")
        cushion_band = c2.selectbox("芝クッション帯", ["未指定","低","中","高"], key=f"surface_cushion_{race_key}") if surface == "芝" else None

        bias_mode = st.segmented_control("当日Bias", ["AUTO (Past-Only)", "手動"], default="AUTO (Past-Only)", key=f"bias_mode_{race_key}")
        hist, _, _ = get_rd_data()
        auto_bias = estimate_same_day_bias(hist, d, venue, surface, race_no)
        if bias_mode == "AUTO (Past-Only)":
            fb_bias = auto_bias["front_back_bias"]
            io_bias = auto_bias["inside_outside_bias"]
            b1, b2, b3 = st.columns(3)
            b1.metric("前後Bias", auto_bias["label_fb"], f"{fb_bias:+.2f}")
            b2.metric("内外Bias", auto_bias["label_io"], f"{io_bias:+.2f}")
            b3.metric("参照済みレース", f"{auto_bias['sample_races']}R")
            st.caption("AUTOは同日・同場・同芝ダの当該Rより前に終了したレースだけを参照します。0Rならフラットです。")
        else:
            fb_map = {"前有利":1.0,"やや前有利":0.5,"フラット":0.0,"やや差し有利":-0.5,"差し有利":-1.0}
            io_map = {"内有利":1.0,"やや内有利":0.5,"フラット":0.0,"やや外有利":-0.5,"外有利":-1.0}
            b1, b2 = st.columns(2)
            fb_label = b1.selectbox("前後Bias手動", list(fb_map), index=2, key=f"fb_manual_{race_key}")
            io_label = b2.selectbox("内外Bias手動", list(io_map), index=2, key=f"io_manual_{race_key}")
            fb_bias, io_bias = fb_map[fb_label], io_map[io_label]

        if st.button("🌱 Final Nexusを計算", use_container_width=True, key=f"surface_apply_{race_key}"):
            with_bias = add_bias_fit(nexus, fb_bias, io_bias)
            final = apply_surface_adjustment(
                with_bias,
                surface=surface,
                going=None if going == "未指定" else going,
                cushion_band=None if cushion_band in (None, "未指定") else cushion_band,
                front_back_fit_col="front_back_fit",
                inside_outside_fit_col="inside_outside_fit",
            )
            st.session_state[f"final_{race_key}"] = final

        final = st.session_state.get(f"final_{race_key}")
        if final is not None:
            final = final.copy()
            final["Nexus Base"] = (final["nexus_base_prob"] * 100).round(1)
            final["Final Nexus"] = (final["final_nexus_prob"] * 100).round(1)
            final["Surfaceβ"] = final["sire_surface_adjustment"].round(2)
            final["DayBiasβ"] = final["day_bias_adjustment"].round(3)
            cols = [c for c in ["馬番","馬名","今回想定脚質","最終角進路","Nexus Base","Surfaceβ","DayBiasβ","Final Nexus"] if c in final.columns]
            st.dataframe(final[cols].sort_values("Final Nexus", ascending=False), use_container_width=True, hide_index=True)

            st.markdown("#### ⑤ 本命連動相手 / Partner Compatibility")
            st.caption("調教で選んだ◎本命が好走するレース形を前提に、能力60%・展開25%・血統10%・馬場5%で相手を順位付けします。調教は本命選定で使うためPartnerへ再加点しません。地雷は除外対象です。Partner Scoreは条件付き複勝率ではなく相対スコアです。")
            anchor_df = anchor_candidates(final)
            anchor_labels = []
            anchor_map = {}
            for _, ar in anchor_df.iterrows():
                no = int(ar["馬番"])
                eligible = bool(ar.get("partner_anchor_eligible", False))
                mark = "◎候補" if eligible else "候補外"
                stars = "★" * int(pd.to_numeric(ar.get("training_stars", 0), errors="coerce") or 0)
                label = f"{no}番 {ar['馬名']} ｜ {mark} {stars}"
                anchor_labels.append(label)
                anchor_map[label] = no
            default_idx = 0
            anchor_label = st.selectbox("◎本命を選択", anchor_labels, index=default_idx, key=f"partner_anchor_{race_key}")
            exclude_jirai = st.checkbox("相手候補から地雷ラップ馬を除外", value=True, key=f"partner_exclude_jirai_{race_key}")
            anchor_no = anchor_map[anchor_label]
            anchor_row = final[pd.to_numeric(final["馬番"], errors="coerce").eq(anchor_no)].iloc[0]
            if not bool(anchor_df[pd.to_numeric(anchor_df["馬番"], errors="coerce").eq(anchor_no)]["partner_anchor_eligible"].iloc[0]):
                st.warning("選択馬は『高勝率A3または調教師判定○＋地雷なし』の◎本命候補条件外です。分析は可能ですが、Ver.3本命基準からは外れます。")
            partners = rank_partners(final, anchor_no, exclude_jirai=exclude_jirai)
            if not partners.empty:
                top_partner = partners.head(3).copy()
                pc_cols = ["馬番","馬名","Partner Score","展開連動","血統共有","馬場連動","調教状態","単体好走力","理由"]
                st.dataframe(top_partner[pc_cols], use_container_width=True, hide_index=True)
                st.markdown("##### 本命連動 TOP 3")
                pcols = st.columns(min(3, len(top_partner)))
                for col, (_, pr) in zip(pcols, top_partner.iterrows()):
                    with col:
                        st.metric(f"{int(pr['馬番'])}番 {pr['馬名']}", f"Partner {pr['Partner Score']:.1f}")
                        st.caption(pr["理由"])
            else:
                st.info("条件に合う相手候補がありません。")

            st.markdown("#### ⑥ Odds / VALUE")
            odds_key = f"odds_{race_key}"
            refresh = st.button("🔄 選択レースの単勝オッズ取得 / 更新", use_container_width=True, key=f"odds_btn_{race_key}")
            if refresh or odds_key not in st.session_state:
                horses = [
                    {"horse_no": int(r["馬番"]), "horse_name": str(r["馬名"])}
                    for _, r in current.iterrows()
                    if pd.notna(r.get("馬番"))
                ]
                with st.spinner("単勝オッズ取得中..."):
                    odds_data, odds_errors = fetch_win_odds(d, venue, race_no, horses, force_update=refresh)
                st.session_state[odds_key] = odds_data
                st.session_state[f"odds_errors_{race_key}"] = odds_errors

            odds_data = st.session_state.get(odds_key, {})
            val = final.copy()
            val["単勝オッズ"] = val["馬番"].map(lambda n: odds_data.get(int(n), {}).get("odds") if pd.notna(n) else None)
            val["人気"] = val["馬番"].map(lambda n: odds_data.get(int(n), {}).get("popularity") if pd.notna(n) else None)
            val = add_value_metrics(val, odds_col="単勝オッズ", prob_col="final_nexus_prob")
            val["Final Nexus"] = (val["final_nexus_prob"] * 100).round(1)
            val["適正オッズ"] = val["Nexus適正オッズ"].round(1)
            val["VALUE"] = val["VALUE"].round(2)
            def value_tag(v):
                if pd.isna(v): return "-"
                if v >= 1.30: return "🔥 強い妙味"
                if v >= 1.10: return "◎ 妙味"
                if v >= 0.95: return "○ 適正"
                return "△ 売れすぎ"
            val["VALUE判定"] = val["VALUE"].map(value_tag)
            val["NEXUS判定"] = val.apply(_nexus_tag, axis=1)
            vcols = [c for c in ["馬番","馬名","NEXUS判定","Final Nexus","単勝オッズ","人気","適正オッズ","VALUE","VALUE判定"] if c in val.columns]
            st.dataframe(val[vcols].sort_values(["VALUE","Final Nexus"], ascending=False, na_position="last"), use_container_width=True, hide_index=True)

            # Partner Ver.3 formal selection:
            # 1) anchor is excluded by rank_partners()
            # 2) Jirai is excluded from the candidate pool
            # 3) market main line = the two most popular remaining candidates
            # 4) NEXUS linked longshot = highest Partner Score outside those two
            st.markdown("##### Partner Ver.3 正式相手選定")
            if not partners.empty:
                formal_pc = partners.copy()
                formal_pc["人気"] = formal_pc["馬番"].map(lambda n: odds_data.get(int(n), {}).get("popularity") if pd.notna(n) else None)
                formal_pc["単勝オッズ"] = formal_pc["馬番"].map(lambda n: odds_data.get(int(n), {}).get("odds") if pd.notna(n) else None)
                pop_known = formal_pc[pd.to_numeric(formal_pc["人気"], errors="coerce").notna()].copy()
                if not pop_known.empty:
                    pop_known["人気_num"] = pd.to_numeric(pop_known["人気"], errors="coerce")
                    market_main = pop_known.sort_values(["人気_num", "Partner Score"], ascending=[True, False]).head(2)
                    market_nos = set(pd.to_numeric(market_main["馬番"], errors="coerce").dropna().astype(int).tolist())
                    nexus_pool = formal_pc[~pd.to_numeric(formal_pc["馬番"], errors="coerce").fillna(-1).astype(int).isin(market_nos)].copy()
                    nexus_hole = nexus_pool.sort_values(["Partner Score","MC複勝率","Final Nexus"], ascending=False).head(1)
                    c1, c2 = st.columns([1,1])
                    with c1:
                        st.markdown("**市場本線（本命を除く・地雷除外の人気上位2頭）**")
                        for _, rr in market_main.iterrows():
                            odds_txt = f" / {rr['単勝オッズ']:.1f}倍" if pd.notna(rr.get("単勝オッズ")) else ""
                            st.write(f"{int(rr['馬番'])}番 {rr['馬名']}｜{int(rr['人気_num'])}人気{odds_txt}｜Partner {rr['Partner Score']:.1f}")
                    with c2:
                        st.markdown("**🔥 NEXUS連動穴（市場本線外のPartner最上位）**")
                        if not nexus_hole.empty:
                            rr = nexus_hole.iloc[0]
                            pop_txt = f"{int(rr['人気'])}人気" if pd.notna(rr.get("人気")) else "人気不明"
                            odds_txt = f" / {rr['単勝オッズ']:.1f}倍" if pd.notna(rr.get("単勝オッズ")) else ""
                            st.write(f"{int(rr['馬番'])}番 {rr['馬名']}｜{pop_txt}{odds_txt}｜Partner {rr['Partner Score']:.1f}")
                            st.caption(rr["理由"])
                        else:
                            st.caption("市場本線以外の候補がありません。")
                else:
                    st.info("人気情報が取得できないため市場本線とNEXUS連動穴の分離は保留します。Partner順位自体は上段で確認できます。")

            top_final = val.sort_values(["Final Nexus","VALUE"], ascending=False, na_position="last").head(3)
            if not top_final.empty:
                st.markdown("##### FINAL NEXUS TOP 3")
                cols = st.columns(len(top_final))
                for col, (_, hr) in zip(cols, top_final.iterrows()):
                    with col:
                        tag = hr.get("NEXUS判定", "") or "Nexus上位"
                        st.metric(f"{int(hr['馬番'])}番 {hr['馬名']}", f"{hr['Final Nexus']:.1f}%")
                        st.caption(tag)
                        if pd.notna(hr.get("VALUE")):
                            st.caption(f"VALUE {hr['VALUE']:.2f} ｜ {hr.get('VALUE判定','-')}")
            errors = st.session_state.get(f"odds_errors_{race_key}", [])
            if errors:
                with st.expander("オッズ取得メモ", expanded=False):
                    st.caption("発売前・過去日・通信失敗時はオッズが空欄でもNexus分析自体は継続します。")
                    for e in errors[-8:]: st.write(e)

elif page == "🌱 Track Condition":
    st.subheader("TRACK CONDITION / SURFACE")
    st.write("Ver.1：種牡馬Surface補正 + 当日Past-Only Bias × RaceDevelopment想定脚質/想定進路")
    st.code("芝: サトノアラジン×高 +0.36 / キタサンブラック×低 +0.30\nダート: 検証済み種牡馬×良/稍重/重/不良βのみ")

else:
    st.subheader("SETTINGS")
    st.write("Nexus Base weights: modules/nexus_probability.py")
    st.write("Pedigree Core: modules/pedigree_core.py")
    st.write("Race Development formal model: modules/race_development_core.py + rd_modules/")
