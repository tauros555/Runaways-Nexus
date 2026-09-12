import joblib
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parents[1]
import numpy as np
import pandas as pd
QUEUE_MODEL_PATH=BASE_DIR/"models/formal_queue_models.joblib"
FULLWIN_MODEL_PATH=BASE_DIR/"models/formal_fullwin_distill.joblib"
_QUEUE=None
_FULL=None

def load_queue():
    global _QUEUE
    if _QUEUE is None: _QUEUE=joblib.load(QUEUE_MODEL_PATH)
    return _QUEUE

def load_full():
    global _FULL
    if _FULL is None: _FULL=joblib.load(FULLWIN_MODEL_PATH)
    return _FULL

def _queue_frame(x):
    b=load_queue(); z=x.copy()
    rename={"HorseLead5":"HorseLeadPast5","HorseFirst5":"HorseFirstPast5","Horse3_5":"Horse3Past5","Horse4_5":"Horse4Past5","HorseFinish5":"HorseFinishPast5","HorseMoveTo3_5":"HorseMoveTo3Past5","HorseMove34_5":"HorseMove34Past5","HorsePCI5":"HorsePCIPast5","Jockey3_50":"Jockey3Pos50","Jockey4_50":"Jockey4Pos50"}
    z=z.rename(columns={k:v for k,v in rename.items() if k in z.columns})
    z["PlaceCode"]=z["場所"].astype(str).map(b["place_map"]).fillna(-1)
    surf=z["芝・ダ"].astype(str).replace({"ダート":"ダ"}); z["SurfaceCode"]=surf.map(b["surface_map"]).fillna(-1)
    z["JockeyLead_x_FirstTurn"]=z["JockeyLead50"]*z["FirstTurnPressure"]
    z["JockeyMoveTo3_x_Close"]=z["JockeyMoveTo3_50"]*z["ClosingOpportunity"]
    med=pd.Series(b["medians"])
    for c in b["features"]:
        if c not in z.columns: z[c]=np.nan
        z[c]=pd.to_numeric(z[c],errors="coerce")
    return z,z[b["features"]].fillna(med).fillna(0).to_numpy(np.float32)

def predict_queue(x):
    b=load_queue(); z,X=_queue_frame(x)
    z["LeadProb_Jockey"]=np.clip(b["models"]["lead"].predict_proba(X)[:,1],0,1)
    z["FirstPred_Jockey"]=np.clip(b["models"]["first"].predict(X),0,1)
    z["ThreePred"]=np.clip(b["models"]["three"].predict(X),0,1)
    z["FourPred_Jockey"]=np.clip(b["models"]["four"].predict(X),0,1)
    zn=z.copy()
    for k,v in {"JockeyRideN":10,"JockeyLead50":0.08,"JockeyFirst50":0.50,"Jockey3Pos50":0.50,"Jockey4Pos50":0.50,"JockeyMoveTo3_50":0.0,"JockeyMove34_50":0.0,"JockeyFinish50":0.50}.items(): zn[k]=v
    zn["JockeyLead_x_FirstTurn"]=zn["JockeyLead50"]*zn["FirstTurnPressure"]
    zn["JockeyMoveTo3_x_Close"]=zn["JockeyMoveTo3_50"]*zn["ClosingOpportunity"]
    med=pd.Series(b["medians"]); Xn=zn[b["features"]].fillna(med).fillna(0).to_numpy(np.float32)
    z["FourPred_NoJockey"]=np.clip(b["models"]["four"].predict(Xn),0,1)
    z["JockeyLift4"]=z["FourPred_Jockey"]-z["FourPred_NoJockey"]
    return z

def predict_fullwin(x):
    b=load_full(); z=x.copy(); med=pd.Series(b["medians"])
    for c in b["features"]:
        if c not in z.columns: z[c]=np.nan
        z[c]=pd.to_numeric(z[c],errors="coerce")
    z["FullWinProb"]=np.clip(b["model"].predict(z[b["features"]].fillna(med).fillna(0)),0,1)
    return z
