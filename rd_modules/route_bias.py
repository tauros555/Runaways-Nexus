from __future__ import annotations
import html
import numpy as np
import pandas as pd

BIAS_LABELS = ["内有利","やや内有利","フラット","やや外有利","外有利"]
LANES = ["内","中","外"]
FIRST_ZONES = ["ハナ","先行","好位","中団","後方"]
FINAL_ZONES = ["先頭","先行","好位","中団","後方"]

BIAS_STRENGTH = {
    "内有利": 1.0,
    "やや内有利": 0.5,
    "フラット": 0.0,
    "やや外有利": -0.5,
    "外有利": -1.0,
}

def resolve_auto_bias(course: dict) -> tuple[str,str]:
    """
    AUTO uses only the course master reference when it is explicit.
    It deliberately does NOT assume that '重/不良 = 外有利' because that is
    not universally true. If course evidence is absent, AUTO is flat.
    """
    text=str(course.get("参考枠傾向","") or "").strip()
    if not text or text.lower()=="nan":
        return "フラット","コースマスタに明示的な進路傾向がないためAUTO=フラット"
    if "やや内" in text or "内寄り" in text or "内～中" in text:
        return "やや内有利",f"コース参考枠傾向: {text}"
    if "内有利" in text or text=="内" or "外から先行しにくい" in text:
        return "内有利",f"コース参考枠傾向: {text}"
    if "やや外" in text or "中～外" in text:
        return "やや外有利",f"コース参考枠傾向: {text}"
    if text=="外":
        return "外有利",f"コース参考枠傾向: {text}"
    if "フラット" in text or "外も" in text or "極端" in text:
        return "フラット",f"コース参考枠傾向: {text}"
    return "フラット",f"参考枠傾向 '{text}' はAUTO補正対象外のためフラット"

def _lane_from_score(v: float) -> str:
    if v <= 0.36: return "内"
    if v >= 0.64: return "外"
    return "中"

def _zone_from_rank(rank:int,n:int,first:bool) -> str:
    if n<=1:
        return "ハナ" if first else "先頭"
    rate=(rank-1)/(n-1)
    labels=FIRST_ZONES if first else FINAL_ZONES
    if rate <= .08: return labels[0]
    if rate <= .30: return labels[1]
    if rate <= .52: return labels[2]
    if rate <= .78: return labels[3]
    return labels[4]

def assign_route_positions(df:pd.DataFrame, course:dict, bias_label:str) -> pd.DataFrame:
    x=df.copy()
    n=max(len(x),1)
    gate=pd.to_numeric(x.get("GateRate",0.5),errors="coerce").fillna(.5).clip(0,1)
    lead=pd.to_numeric(x.get("LeadProb_Jockey",.08),errors="coerce").fillna(.08).clip(0,1)
    first=pd.to_numeric(x.get("FirstPred_Jockey",.5),errors="coerce").fillna(.5).clip(0,1)
    four=pd.to_numeric(x.get("Pred4Scenario",x.get("FourPred_Jockey",.5)),errors="coerce").fillna(.5).clip(0,1)
    move=pd.to_numeric(x.get("Move_First_to_4",0),errors="coerce").fillna(0)
    close=float(course.get("ClosingOpportunity",.5) or .5)
    ft=float(course.get("FirstTurnPressure",.5) or .5)

    # 0=inside, 1=outside. Front speed can allow outer-drawn horses to cut in.
    first_lane=(0.68*gate - 0.22*lead - 0.12*first + 0.08*ft).clip(0,1)
    x["初角進路指数"]=first_lane
    x["初角進路"]=first_lane.map(_lane_from_score)

    # Late outside tendency: initial lane + closing profile + advancing from the rear.
    closing=(1-four).clip(0,1)
    advance=(move.clip(-5,5)+5)/10
    final_lane=(0.42*first_lane + 0.28*closing*close + 0.18*advance + 0.12*gate).clip(0,1)
    x["最終角進路指数"]=final_lane
    x["最終角進路"]=final_lane.map(_lane_from_score)

    fr=pd.to_numeric(x["PredFirstRank"],errors="coerce").fillna(n).astype(int)
    qr=pd.to_numeric(x["Pred4ScenarioRank"],errors="coerce").fillna(n).astype(int)
    x["初角ゾーン"]=[_zone_from_rank(int(r),n,True) for r in fr]
    x["最終角ゾーン"]=[_zone_from_rank(int(r),n,False) for r in qr]

    strength=BIAS_STRENGTH.get(bias_label,0.0)
    # lane_value: inside=+1, middle=0, outside=-1.
    lane_value=x["最終角進路"].map({"内":1.0,"中":0.0,"外":-1.0}).fillna(0)
    # Bounded route correction. Max +/- 4 percentage points.
    x["進路バイアス補正"]=0.04*strength*lane_value
    base=pd.to_numeric(x.get("ScenarioFullWinProb",x.get("FullWinProb",0)),errors="coerce").fillna(0)
    x["進路補正後勝率ベース"]=np.clip(base+x["進路バイアス補正"],0.001,0.95)

    def impact(v):
        if v>=.025:return "恩恵＋＋"
        if v>=.010:return "恩恵＋"
        if v<=-.025:return "不利－－"
        if v<=-.010:return "不利－"
        return "影響小"
    x["進路バイアス評価"]=x["進路バイアス補正"].map(impact)
    return x

def _esc(v): return html.escape(str(v))

def _card(r,rank_col):
    try:num=int(r["馬番"])
    except:num="-"
    try:rank=int(r[rank_col])
    except:rank="-"
    grade=str(r.get("展開評価",""))
    impact=str(r.get("進路バイアス評価",""))
    return (
        "<div class='rz-card'>"
        f"<span class='rz-num'>{num}</span>"
        "<span class='rz-main'>"
        f"<b>{_esc(r.get('馬名',''))} {_esc(grade)}</b>"
        f"<small>{_esc(r.get('騎手',''))} / {_esc(impact)}</small>"
        "</span>"
        f"<span class='rz-rank'>{rank}</span>"
        "</div>"
    )

def render_route_grid(df:pd.DataFrame,stage:str,bias_label:str) -> str:
    first=stage=="初角"
    zone_col="初角ゾーン" if first else "最終角ゾーン"
    lane_col="初角進路" if first else "最終角進路"
    rank_col="PredFirstRank" if first else "Pred4ScenarioRank"
    zones=FIRST_ZONES if first else FINAL_ZONES
    x=df.copy()

    cells=[]
    for lane in LANES:
        for zone in zones:
            z=x[(x[lane_col]==lane)&(x[zone_col]==zone)].sort_values(rank_col)
            cards="".join(_card(r,rank_col) for _,r in z.iterrows()) or "<div class='rz-empty'>—</div>"
            cells.append(f"<div class='rz-cell'><div class='rz-cell-inner'>{cards}</div></div>")

    css="""
    <style>
    .rz-wrap{border:1px solid rgba(128,128,128,.28);border-radius:16px;overflow:hidden;margin:10px 0 18px}
    .rz-head{display:flex;justify-content:space-between;align-items:center;padding:11px 14px;font-weight:900}
    .rz-sub{font-size:11px;opacity:.70;font-weight:500}
    .rz-grid{display:grid;grid-template-columns:62px repeat(5,minmax(150px,1fr));}
    .rz-corner{padding:8px;font-size:11px;opacity:.65;border-top:1px solid rgba(128,128,128,.18)}
    .rz-zone{padding:8px;text-align:center;font-weight:900;font-size:12px;border-top:1px solid rgba(128,128,128,.18)}
    .rz-lane{padding:12px 8px;font-weight:900;text-align:center;border-top:1px solid rgba(128,128,128,.18);display:flex;align-items:center;justify-content:center}
    .rz-cell{min-height:92px;padding:7px;border-left:1px solid rgba(128,128,128,.15);border-top:1px solid rgba(128,128,128,.18)}
    .rz-cell-inner{display:flex;flex-direction:column;gap:5px}
    .rz-card{display:grid;grid-template-columns:26px 1fr 24px;gap:6px;align-items:center;border:1px solid rgba(128,128,128,.26);border-radius:9px;padding:6px;background:rgba(128,128,128,.055)}
    .rz-num{width:24px;height:24px;border-radius:50%;border:1px solid rgba(128,128,128,.35);display:flex;align-items:center;justify-content:center;font-weight:900;font-size:11px}
    .rz-main{min-width:0}.rz-main b{display:block;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rz-main small{display:block;font-size:9px;opacity:.65;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .rz-rank{text-align:center;font-size:11px;font-weight:900}
    .rz-empty{text-align:center;opacity:.25;padding:10px}
    @media(max-width:1000px){.rz-grid{grid-template-columns:48px repeat(5,minmax(125px,1fr));overflow-x:auto}.rz-card{grid-template-columns:22px 1fr 20px}.rz-main small{display:none}}
    </style>
    """
    headers="<div class='rz-corner'>進路</div>"+"".join(f"<div class='rz-zone'>{z}</div>" for z in zones)
    body=""
    idx=0
    for lane in LANES:
        body+=f"<div class='rz-lane'>{lane}</div>"
        for _ in zones:
            body+=cells[idx]; idx+=1
    title="初角隊列" if first else "最終コーナー隊列"
    return (
        css+"<div class='rz-wrap'>"
        f"<div class='rz-head'><span>{title}</span><span class='rz-sub'>進行方向 ←　|　馬場・進路バイアス {bias_label}</span></div>"
        f"<div class='rz-grid'>{headers}{body}</div></div>"
    )
