import numpy as np
import pandas as pd

SCENARIOS=["SLOW","EVEN","HIGH","SPRINT_FINISH","LONG_SPURT"]


def _scenario_components(df: pd.DataFrame, scenario: str):
    z=df
    if scenario=="SLOW":
        adj4=0.035*(z["FirstPred_Jockey"].to_numpy(float)-0.5)
        adjf=0.035*(z["FourPred_Jockey"].to_numpy(float)-0.5)
    elif scenario=="HIGH":
        adj4=-0.055*z["FrontExposure"].to_numpy(float)+0.045*z["ClosingRelief"].to_numpy(float)
        adjf=-0.070*z["FrontExposure"].to_numpy(float)+0.060*z["ClosingRelief"].to_numpy(float)
    elif scenario=="SPRINT_FINISH":
        close=(1-z["FourPred_Jockey"].to_numpy(float))*z["ClosingOpportunity"].to_numpy(float)
        adj4=0.015*close
        adjf=0.060*close
    elif scenario=="LONG_SPURT":
        if "HorseMoveTo3_5" in z.columns:
            move=np.clip(0.5+pd.to_numeric(z["HorseMoveTo3_5"],errors="coerce").fillna(0).to_numpy(float),0,1)
        else:
            move=np.full(len(z),0.5)
        adj4=0.045*(move-0.5)
        adjf=0.055*(move-0.5)
    else:
        adj4=np.zeros(len(z)); adjf=np.zeros(len(z))
    four=np.clip(z["FourPred_Jockey"].to_numpy(float)+adj4,0,1)
    base_col="進路補正後勝率ベース" if "進路補正後勝率ベース" in z.columns else "FullWinProb"
    p=np.clip(z[base_col].to_numpy(float)+adjf,0.001,0.95)
    return four,p


def _wilson(k,n,z=1.96):
    if n<=0: return (np.nan,np.nan)
    ph=k/n; den=1+z*z/n
    ctr=(ph+z*z/(2*n))/den
    rad=z*np.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/den
    return max(0,ctr-rad),min(1,ctr+rad)


def simulate_race(df: pd.DataFrame, scenario_info: dict, n_sims: int=1000, mode: str="AUTO", seed: int=5601):
    """Monte Carlo race simulation.

    AUTO samples a race scenario from the model's 5-class probabilities each trial.
    Manual mode fixes that scenario for every trial.
    Output probabilities are simulation-derived estimates, not a separate calibrated odds model.
    """
    x=df.reset_index(drop=True).copy()
    n=len(x)
    if n<2:
        raise ValueError("2頭以上必要です。")
    rng=np.random.default_rng(seed)

    probs=np.array([
        scenario_info.get("P_SLOW",0),scenario_info.get("P_EVEN",0),scenario_info.get("P_HIGH",0),
        scenario_info.get("P_SPRINT_FINISH",0),scenario_info.get("P_LONG_SPURT",0)
    ],dtype=float)
    if probs.sum()<=0: probs=np.array([0,1,0,0,0],dtype=float)
    probs=probs/probs.sum()
    if mode=="AUTO":
        scen_idx=rng.choice(len(SCENARIOS),size=n_sims,p=probs)
    else:
        scen_idx=np.full(n_sims,SCENARIOS.index(mode),dtype=int)

    first_mu=np.clip(x["FirstPred_Jockey"].to_numpy(float),0,1)
    three_mu=np.clip(x["ThreePred"].to_numpy(float),0,1)
    lead_p=np.clip(x["LeadProb_Jockey"].to_numpy(float),0.001,0.999)

    # Reliability-driven uncertainty: sparse horse history -> wider queue uncertainty.
    hn=pd.to_numeric(x.get("HorseHistoryN",pd.Series(np.zeros(n))),errors="coerce").fillna(0).to_numpy(float)
    reliability=np.clip(hn/5.0,0,1)
    sig_first=0.11+0.08*(1-reliability)
    sig_three=0.16+0.09*(1-reliability)
    sig_four=0.16+0.09*(1-reliability)

    win=np.zeros(n,dtype=int); top2=np.zeros(n,dtype=int); top3=np.zeros(n,dtype=int)
    lead=np.zeros(n,dtype=int); four_top3=np.zeros(n,dtype=int)
    finish_sum=np.zeros(n,dtype=float); four_rank_sum=np.zeros(n,dtype=float)
    scenario_wins={s:np.zeros(n,dtype=int) for s in SCENARIOS}
    scenario_counts={s:0 for s in SCENARIOS}

    # Batch by scenario for speed and to preserve shared race environment.
    for si,s in enumerate(SCENARIOS):
        idx=np.flatnonzero(scen_idx==si); m=len(idx)
        if m==0: continue
        scenario_counts[s]=m
        four_mu,base_p=_scenario_components(x,s)

        first=np.clip(first_mu+rng.normal(0,sig_first,size=(m,n)),0,1)
        three=np.clip(three_mu+rng.normal(0,sig_three,size=(m,n)),0,1)
        four=np.clip(four_mu+rng.normal(0,sig_four,size=(m,n)),0,1)

        # One race leader: categorical race against Gumbel noise using model LeadProb.
        lead_util=np.log(lead_p)[None,:]+rng.gumbel(0,1,size=(m,n))
        leaders=lead_util.argmax(axis=1)
        np.add.at(lead,leaders,1)

        # Finish utility combines scenario-conditioned strength, queue realization,
        # and irreducible race-day variation (Gumbel -> coherent race ranking).
        queue_delta=0.32*(four-four_mu[None,:])+0.12*(three-three_mu[None,:])+0.06*(first-first_mu[None,:])
        utility=np.log(base_p)[None,:]+queue_delta+rng.gumbel(0,1,size=(m,n))
        order=np.argsort(-utility,axis=1)
        winners=order[:,0]
        np.add.at(win,winners,1); np.add.at(scenario_wins[s],winners,1)
        for rnk in range(min(3,n)):
            ids=order[:,rnk]
            if rnk<2: np.add.at(top2,ids,1)
            np.add.at(top3,ids,1)
        ranks=np.empty_like(order)
        rr=np.arange(m)[:,None]
        ranks[rr,order]=np.arange(1,n+1)[None,:]
        finish_sum+=ranks.sum(axis=0)

        four_order=np.argsort(-four,axis=1)
        four_ranks=np.empty_like(four_order)
        four_ranks[rr,four_order]=np.arange(1,n+1)[None,:]
        four_rank_sum+=four_ranks.sum(axis=0)
        for rnk in range(min(3,n)):
            np.add.at(four_top3,four_order[:,rnk],1)

    out=x[[c for c in ["馬番","馬名","騎手","今回想定脚質","展開評価","FullWinProb"] if c in x.columns]].copy()
    out["MC勝率"]=win/n_sims
    out["MC連対率"]=top2/n_sims
    out["MC複勝率"]=top3/n_sims
    out["MC逃げ率"]=lead/n_sims
    out["MC4角3番手内率"]=four_top3/n_sims
    out["MC平均着順"]=finish_sum/n_sims
    out["MC平均4角順位"]=four_rank_sum/n_sims
    out["MC勝利回数"]=win
    lows=[]; highs=[]
    for k in win:
        lo,hi=_wilson(int(k),n_sims); lows.append(lo); highs.append(hi)
    out["MC勝率95%下限"]=lows; out["MC勝率95%上限"]=highs
    for s in SCENARIOS:
        c=scenario_counts[s]
        out[f"{s}_勝率"]=(scenario_wins[s]/c) if c else np.nan
    out=out.sort_values(["MC勝率","MC複勝率"],ascending=False).reset_index(drop=True)
    meta={
        "n_sims":int(n_sims),"mode":mode,"seed":int(seed),
        "scenario_counts":scenario_counts,
        "win_rate_sum":float(out["MC勝率"].sum()),
    }
    return out,meta
