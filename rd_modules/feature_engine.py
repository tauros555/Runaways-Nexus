import pandas as pd, numpy as np
from rd_modules.distance_change import distance_change_bucket
def enrich(h):
    h=h.copy(); n=pd.to_numeric(h["頭数"],errors="coerce")
    ranks=[]
    for src,dst in [("通過順位1角","P1"),("通過順位2角","P2"),("通過順位3角","P3"),("通過順位4角","P4")]:
        r=pd.to_numeric(h[src],errors="coerce")
        # 0は未使用コーナー・欠測。実順位として扱わない。
        r=r.where((n>1)&r.between(1,n)&r.eq(r.round()))
        ranks.append(r)
        h[dst]=1-(r-1)/(n-1)
    finish=pd.to_numeric(h["確定着順"],errors="coerce")
    finish=finish.where((n>1)&finish.between(1,n)&finish.eq(finish.round()))
    h["FinishRate"]=1-(finish-1)/(n-1)
    h["FirstRate"]=h[["P1","P2","P3","P4"]].bfill(axis=1).iloc[:,0]
    h["MoveTo3"]=h["P3"]-h["FirstRate"]; h["Move34"]=h["P4"]-h["P3"]
    first_rank=pd.concat(ranks,axis=1).bfill(axis=1).iloc[:,0]
    # 全コーナー不明なら「先頭ではなかった」とせず、集計から除外する。
    h["LeadObserved"]=first_rank.eq(1).astype(float).where(first_rank.notna())
    return h
def mean(s,d):
    v=pd.to_numeric(s,errors="coerce").dropna(); return float(v.mean()) if len(v) else d
def build_features(e,h,course):
    h=enrich(h); out=e.copy()
    if "血統登録番号" not in out.columns: out["血統登録番号"]=""
    out["血統登録番号"]=out["血統登録番号"].astype(str).str.replace(r"\.0$","",regex=True)
    td=pd.to_numeric(out.get("年月日",pd.Series([99999999]*len(out))),errors="coerce").fillna(99999999).max()
    h=h[pd.to_numeric(h["date"],errors="coerce")<td]
    # 履歴全件を馬・騎手ごとに繰り返し走査せず、先にキー別に分割する。
    # 各グループの並べ替えとtailは従来と同じ演算で、特徴量を変更しない。
    h_horse_groups={k:g for k,g in h.groupby(h["血統登録番号"].astype(str),sort=False)}
    h_jockey_groups={k:g for k,g in h.groupby(h["騎手"].astype(str),sort=False)}
    empty_history=h.iloc[0:0]
    rows=[]
    for _,r in out.iterrows():
        hid=str(r.get("血統登録番号","")); hn=h_horse_groups.get(hid,empty_history).sort_values("date").tail(5) if hid and hid!="nan" else empty_history
        jn=str(r.get("騎手","")); jk=h_jockey_groups.get(jn,empty_history).sort_values("date").tail(50) if jn and jn!="nan" else empty_history
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
