import joblib
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parents[1]
import numpy as np
import pandas as pd

MODEL_PATH=BASE_DIR/"models/scenario5_formal.joblib"
HORSE_SD_PATH=BASE_DIR/"data/rd/horse_startdash_tracking.csv"
_MODEL=None
_SD=None

def _load_model():
    global _MODEL
    if _MODEL is None:
        _MODEL=joblib.load(MODEL_PATH)
    return _MODEL

def _load_sd():
    global _SD
    if _SD is None:
        _SD=pd.read_csv(HORSE_SD_PATH,encoding="cp932",low_memory=False)
        _SD["血統登録番号"]=_SD["血統登録番号"].astype(str).str.replace(r"\.0$","",regex=True)
    return _SD

def build_race_features(pred:pd.DataFrame, raceinfo:dict):
    sd=_load_sd()
    x=pred.copy()
    x["血統登録番号"]=x.get("血統登録番号","").astype(str).str.replace(r"\.0$","",regex=True)
    x=x.merge(
        sd[["血統登録番号","StartDashScore","EarlyTrackingScore","Reliability","Type"]],
        on="血統登録番号",how="left"
    )
    # Missing/new horses: neutral historical prior.
    x["StartDashScore"]=pd.to_numeric(x["StartDashScore"],errors="coerce").fillna(50.0)
    x["EarlyTrackingScore"]=pd.to_numeric(x["EarlyTrackingScore"],errors="coerce").fillna(50.0)

    sd01=x["StartDashScore"]/100.0
    et01=x["EarlyTrackingScore"]/100.0
    dash_comp=float(sd01.mean() + sd01.std(ddof=0))
    track_comp=float(et01.mean() + et01.std(ddof=0))

    row={
        "距離":float(pd.to_numeric(x["距離"],errors="coerce").iloc[0]),
        "頭数":float(len(x)),
        "FirstTurnPressure":float(pd.to_numeric(x["FirstTurnPressure"],errors="coerce").iloc[0]),
        "FirstTurnDistance":float(pd.to_numeric(x["初角距離m"],errors="coerce").iloc[0]) if "初角距離m" in x.columns else 350.0,
        "FrontDensity":float(raceinfo["FrontDensity"]),
        "LeadDensity":float(raceinfo["LeadDensity"]),
        "LeadCompetitionIndex_v2":float(raceinfo["LeadCompetitionIndex_v2"]),
        "StartDash_mean":float(sd01.mean()),
        "StartDash_max":float(sd01.max()),
        "EarlyTracking_mean":float(et01.mean()),
        "EarlyTracking_max":float(et01.max()),
        "DashCompetitionIndex":dash_comp,
        "TrackingCompetitionIndex":track_comp,
        "DashVsTrackingPressure":dash_comp-track_comp,
    }
    return row,x

def predict_scenario(pred:pd.DataFrame,raceinfo:dict):
    b=_load_model()
    row,enhanced=build_race_features(pred,raceinfo)
    z=pd.DataFrame([row])
    med=pd.Series(b["medians"])
    X=z[b["features"]].apply(pd.to_numeric,errors="coerce").fillna(med).fillna(0)
    p=b["model"].predict_proba(X)[0]
    probs={c:float(v) for c,v in zip(b["model"].classes_,p)}
    best=max(probs,key=probs.get)
    return {
        "PredictedScenario":best,
        "TopProbability":probs[best],
        "P_SLOW":probs.get("SLOW",0.0),
        "P_EVEN":probs.get("EVEN",0.0),
        "P_HIGH":probs.get("HIGH",0.0),
        "P_SPRINT_FINISH":probs.get("SPRINT_FINISH",0.0),
        "P_LONG_SPURT":probs.get("LONG_SPURT",0.0),
        "features":row,
    },enhanced

def scenario_adjustment(df:pd.DataFrame,scenario:str):
    """
    v3 production transform:
    scenario changes queue/finish interpretation, not Runaway's score.
    Small bounded transforms, preserving formal base queue.
    """
    z=df.copy()
    s=scenario
    if s=="SLOW":
        z["Scenario4Adj"]=0.035*(z["FirstPred_Jockey"]-0.5)
        z["ScenarioFinishAdj"]=0.035*(z["FourPred_Jockey"]-0.5)
    elif s=="HIGH":
        z["Scenario4Adj"]=-0.055*z["FrontExposure"]+0.045*z["ClosingRelief"]
        z["ScenarioFinishAdj"]=-0.070*z["FrontExposure"]+0.060*z["ClosingRelief"]
    elif s=="SPRINT_FINISH":
        close=(1-z["FourPred_Jockey"])*z["ClosingOpportunity"]
        z["Scenario4Adj"]=0.015*close
        z["ScenarioFinishAdj"]=0.060*close
    elif s=="LONG_SPURT":
        move=(0.5+z.get("HorseMoveTo3_5",0)).clip(0,1)
        z["Scenario4Adj"]=0.045*(move-0.5)
        z["ScenarioFinishAdj"]=0.055*(move-0.5)
    else:
        z["Scenario4Adj"]=0.0
        z["ScenarioFinishAdj"]=0.0
    z["Pred4Scenario"]=np.clip(z["FourPred_Jockey"]+z["Scenario4Adj"],0,1)
    z["Pred4ScenarioRank"]=z["Pred4Scenario"].rank(method="first",ascending=False).astype(int)
    z["ScenarioFullWinProb"]=np.clip(z["FullWinProb"]+z["ScenarioFinishAdj"],0,1)
    return z
