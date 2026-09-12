import numpy as np
from rd_modules.model_adapter import predict_queue,predict_fullwin
from rd_modules.distance_change import apply_queue_corrections,apply_win_correction

def predict(x):
    z=predict_queue(x)
    # Restore validated course × distance-change correction.
    # Weights were revalidated on 2026 holdout:
    # Lead 0.4 / first-position 1.0 / independent win correction 0.3.
    z=apply_queue_corrections(z)
    lead_density=float(z["LeadProb_Jockey"].mean()); front_density=float((z["FirstPred_Jockey"]>=0.65).mean())
    lci=float(np.clip(0.55*lead_density+0.30*front_density+0.15*float(z["FirstTurnPressure"].iloc[0]),0,1))
    pressure="LOW" if lci<0.55 else ("MID" if lci<0.65 else "HIGH")
    z["LeadCompetitionIndex_v2"]=lci; z["FrontDensity"]=front_density; z["LeadDensity"]=lead_density
    z["FrontExposure"]=z["FourPred_Jockey"]*lci*z["FirstTurnPressure"]
    z["ClosingRelief"]=(1-z["FourPred_Jockey"])*z["ClosingOpportunity"]*lci
    z["FrontCloseTension"]=z["FourPred_Jockey"]*z["ClosingOpportunity"]*lci
    z["LeadPressure"]=z["LeadProb_Jockey"]*lci
    z=predict_fullwin(z)
    z=apply_win_correction(z)
    z["PredFirstRank"]=z["FirstPred_Jockey"].rank(method="first",ascending=False).astype(int)
    z["Pred3Rank"]=z["ThreePred"].rank(method="first",ascending=False).astype(int)
    z["Pred4Rank"]=z["FourPred_Jockey"].rank(method="first",ascending=False).astype(int)
    def style(r):
        if r["LeadProb_Jockey"]>=0.25: return "逃げ"
        if r["FirstPred_Jockey"]>=0.82 and r["FourPred_Jockey"]>=0.68: return "逃げ候補"
        if r["FourPred_Jockey"]>=0.65: return "先行"
        if r["FourPred_Jockey"]>=0.40: return "中団"
        if r["FourPred_Jockey"]>=0.20: return "差し"
        return "追込"
    z["今回想定脚質"]=z.apply(style,axis=1)
    return z,{"LeadCompetitionIndex_v2":lci,"先行圧力":pressure,"LeadDensity":lead_density,"FrontDensity":front_density,"engine":"FORMAL_MODEL_v2+DISTANCE_CHANGE_v1"}

def assign_grade(x,t,year,surface):
    x=x.copy(); surf="芝" if surface=="芝" else "ダ"; z=t[t["芝ダ"]==surf].sort_values("適用年")
    eligible=z[z["適用年"]<=year]; z=eligible.tail(1) if len(eligible) else z.tail(1)
    if not len(z): x["展開評価"]=""; x["展開評価ステータス"]="NO_THRESHOLD"; return x
    q20,q60,q80=[float(z[c].iloc[0]) for c in ["Q20_×上限","Q60_△上限","Q80_○上限"]]
    p=x["FullWinProb"]; x["展開評価"]=np.select([p<=q20,p<=q60,p<=q80],["×","△","○"],default="◎")
    x["展開評価ステータス"]="FORMAL_DISTILLED_v2"; return x
