import pandas as pd, numpy as np
from rd_modules.distance_change import distance_change_bucket
def enrich(h):
    h=h.copy(); n=pd.to_numeric(h["頭数"],errors="coerce")
    for src,dst in [("通過順位1角","P1"),("通過順位2角","P2"),("通過順位3角","P3"),("通過順位4角","P4")]:
        r=pd.to_numeric(h[src],errors="coerce"); h[dst]=1-(r-1)/(n-1); h.loc[(n<=1)|r.isna(),dst]=np.nan
    h["FinishRate"]=1-(pd.to_numeric(h["確定着順"],errors="coerce")-1)/(n-1)
    h["FirstRate"]=h[["P1","P2","P3","P4"]].bfill(axis=1).iloc[:,0]
    h["MoveTo3"]=h["P3"]-h["FirstRate"]; h["Move34"]=h["P4"]-h["P3"]
    first_rank=h[["通過順位1角","通過順位2角","通過順位3角","通過順位4角"]].bfill(axis=1).iloc[:,0]
    h["LeadObserved"]=(pd.to_numeric(first_rank,errors="coerce")==1).astype(float)
    return h
def mean(s,d):
    v=pd.to_numeric(s,errors="coerce").dropna(); return float(v.mean()) if len(v) else d
def build_features(e,h,course):
    h=enrich(h); out=e.copy()
    if "血統登録番号" not in out.columns: out["血統登録番号"]=""
    out["血統登録番号"]=out["血統登録番号"].astype(str).str.replace(r"\.0$","",regex=True)
    td=pd.to_numeric(out.get("年月日",pd.Series([99999999]*len(out))),errors="coerce").fillna(99999999).max()
    h=h[pd.to_numeric(h["date"],errors="coerce")<td]
    rows=[]
    for _,r in out.iterrows():
        hid=str(r.get("血統登録番号","")); hn=h[h["血統登録番号"].astype(str)==hid].sort_values("date").tail(5) if hid and hid!="nan" else h.iloc[0:0]
        jn=str(r.get("騎手","")); jk=h[h["騎手"].astype(str)==jn].sort_values("date").tail(50) if jn and jn!="nan" else h.iloc[0:0]
        prev_dist = pd.to_numeric(hn["距離"],errors="coerce").dropna().iloc[-1] if len(hn) and pd.to_numeric(hn["距離"],errors="coerce").dropna().size else np.nan
        cur_dist = pd.to_numeric(pd.Series([r.get("距離",np.nan)]),errors="coerce").iloc[0]
        dist_change = cur_dist-prev_dist if pd.notna(cur_dist) and pd.notna(prev_dist) else np.nan
        rows.append({
            "HorseHistoryN":len(hn),
            "HorseLead5":mean(hn["LeadObserved"],.08),
            "HorseFirst5":mean(hn["FirstRate"],.5),
            "Horse3_5":mean(hn["P3"],.5),
            "Horse4_5":mean(hn["P4"],.5),
            "HorseMoveTo3_5":mean(hn["MoveTo3"],0),
            "HorseMove34_5":mean(hn["Move34"],0),
            "HorseFinish5":mean(hn["FinishRate"],.5),
            "HorsePCI5":mean(hn["PCI"],50),
            "PrevDistance":prev_dist,
            "DistanceChange":dist_change,
            "距離変化区分":distance_change_bucket(dist_change),
            "JockeyRideN":len(jk),
            "JockeyLead50":mean(jk["LeadObserved"],.08),
            "JockeyFirst50":mean(jk["FirstRate"],.5),
            "Jockey3_50":mean(jk["P3"],.5),
            "Jockey4_50":mean(jk["P4"],.5),
            "JockeyMoveTo3_50":mean(jk["MoveTo3"],0),
            "JockeyMove34_50":mean(jk["Move34"],0),
            "JockeyFinish50":mean(jk["FinishRate"],.5)
        })
    x=pd.concat([out.reset_index(drop=True),pd.DataFrame(rows)],axis=1); n=max(len(x),1); x["GateRate"]=(pd.to_numeric(x["馬番"],errors="coerce")-1)/max(n-1,1)
    for c,d in [("StartDashWeight",.5),("EarlyTrackingWeight",.5),("FirstTurnPressure",.5),("ClosingOpportunity",.5),("LongSpurtOpportunity",.5),("初角距離m",350.0),("最終直線m",350.0)]:
        x[c]=float(course.get(c,d)) if course.get(c,d)==course.get(c,d) else d
    return x
