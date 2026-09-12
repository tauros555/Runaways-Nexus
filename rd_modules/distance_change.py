from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

MASTER_PATH = Path(__file__).resolve().parents[1] / "data/rd/DistanceChangeCorrectionMaster_v1.csv"
_MASTER = None

def distance_change_bucket(v):
    try:
        x=float(v)
    except Exception:
        return "不明"
    if np.isnan(x): return "不明"
    if x <= -400: return "短縮400m+"
    if x <= -200: return "短縮200-399"
    if x < 0: return "短縮1-199"
    if x == 0: return "同距離"
    if x < 200: return "延長1-199"
    if x < 400: return "延長200-399"
    return "延長400m+"

def _load_master():
    global _MASTER
    if _MASTER is None:
        if not MASTER_PATH.exists():
            _MASTER=pd.DataFrame()
        else:
            _MASTER=pd.read_csv(MASTER_PATH,encoding="utf-8-sig",low_memory=False)
            if "距離" in _MASTER.columns:
                _MASTER["距離"]=pd.to_numeric(_MASTER["距離"],errors="coerce")
    return _MASTER

def _lookup(master, place, surface, distance, bucket):
    if master.empty or bucket=="不明":
        return None
    surf="芝" if str(surface)=="芝" else "ダ"
    dist=float(distance)

    # 1) exact course × surface × current distance × change bucket
    z=master[
        (master["level"]=="COURSE")
        &(master["場所"].astype(str)==str(place))
        &(master["surface"].astype(str)==surf)
        &(pd.to_numeric(master["距離"],errors="coerce")==dist)
        &(master["距離変化区分"].astype(str)==bucket)
    ]
    if len(z):
        return z.iloc[0], "COURSE"

    # 2) surface × distance × bucket
    z=master[
        (master["level"]=="SURFACE_DISTANCE")
        &(master["surface"].astype(str)==surf)
        &(pd.to_numeric(master["距離"],errors="coerce")==dist)
        &(master["距離変化区分"].astype(str)==bucket)
    ]
    if len(z):
        return z.iloc[0], "SURFACE_DISTANCE"

    # 3) global bucket
    z=master[
        (master["level"]=="GLOBAL")
        &(master["距離変化区分"].astype(str)==bucket)
    ]
    if len(z):
        return z.iloc[0], "GLOBAL"
    return None

def attach_distance_change_corrections(df:pd.DataFrame) -> pd.DataFrame:
    x=df.copy()
    m=_load_master()
    lead=[]; first=[]; win=[]; src=[]; ns=[]

    for _,r in x.iterrows():
        bucket=str(r.get("距離変化区分","不明"))
        ans=_lookup(
            m,
            r.get("場所",""),
            r.get("芝・ダ",""),
            r.get("距離",np.nan),
            bucket
        )
        if ans is None:
            lead.append(0.0); first.append(0.0); win.append(0.0)
            src.append("NONE"); ns.append(0)
            continue
        row,level=ans
        lead.append(float(pd.to_numeric(row.get("LeadAdj_Prod",0),errors="coerce") or 0))
        first.append(float(pd.to_numeric(row.get("FirstAdj_Prod",0),errors="coerce") or 0))
        win.append(float(pd.to_numeric(row.get("WinAdj_Prod",0),errors="coerce") or 0))
        src.append(level)
        vals=[
            pd.to_numeric(row.get("lead_n",0),errors="coerce"),
            pd.to_numeric(row.get("first_n",0),errors="coerce"),
            pd.to_numeric(row.get("win_n",0),errors="coerce"),
        ]
        vals=[int(v) for v in vals if pd.notna(v)]
        ns.append(max(vals) if vals else 0)

    x["距離変化_Lead補正"]=lead
    x["距離変化_初角補正"]=first
    x["距離変化_勝率補正"]=win
    x["距離変化_補正ソース"]=src
    x["距離変化_学習N"]=ns
    return x

def apply_queue_corrections(df:pd.DataFrame) -> pd.DataFrame:
    x=attach_distance_change_corrections(df)
    x["LeadProb_Base"]=pd.to_numeric(x["LeadProb_Jockey"],errors="coerce")
    x["FirstPred_Base"]=pd.to_numeric(x["FirstPred_Jockey"],errors="coerce")
    x["LeadProb_Jockey"]=np.clip(
        x["LeadProb_Base"]+pd.to_numeric(x["距離変化_Lead補正"],errors="coerce").fillna(0),0,1
    )
    x["FirstPred_Jockey"]=np.clip(
        x["FirstPred_Base"]+pd.to_numeric(x["距離変化_初角補正"],errors="coerce").fillna(0),0,1
    )
    return x

def apply_win_correction(df:pd.DataFrame) -> pd.DataFrame:
    x=df.copy()
    x["FullWinProb_Base"]=pd.to_numeric(x["FullWinProb"],errors="coerce")
    x["FullWinProb"]=np.clip(
        x["FullWinProb_Base"]+pd.to_numeric(x.get("距離変化_勝率補正",0),errors="coerce").fillna(0),
        0,1
    )
    return x

def effect_label(v):
    try: x=float(v)
    except Exception: return "影響なし"
    if x >= .03: return "強いプラス"
    if x >= .01: return "プラス"
    if x <= -.03: return "強いマイナス"
    if x <= -.01: return "マイナス"
    return "小"
