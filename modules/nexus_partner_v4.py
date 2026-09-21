from __future__ import annotations
import pandas as pd
import numpy as np

def _num(v, default=np.nan):
    try:
        z=float(v)
        return default if np.isnan(z) else z
    except Exception:
        return default

def build_partner_recommendations(final: pd.DataFrame, partners: pd.DataFrame, anchor_no: int,
                                  odds_data: dict|None=None, max_total: int=5) -> pd.DataFrame:
    """Nexus partner v4.
    Main line = popular horses excluding effective Jirai.
    Hole line = Simulator/Partner top horses, upgraded by course-training and M-course evidence.
    """
    odds_data=odds_data or {}
    x=final.copy()
    x["馬番_num"]=pd.to_numeric(x["馬番"],errors="coerce")
    x=x[~x["馬番_num"].eq(float(anchor_no))].copy()
    x["地雷_effective"]=pd.to_numeric(x.get("jirai",x.get("jirai_badge",0)),errors="coerce").fillna(0).astype(int)
    x["人気_live"]=x["馬番_num"].map(lambda n: odds_data.get(int(n),{}).get("popularity") if pd.notna(n) else None)
    x["単勝_live"]=x["馬番_num"].map(lambda n: odds_data.get(int(n),{}).get("odds") if pd.notna(n) else None)
    x["人気_live"]=pd.to_numeric(x["人気_live"],errors="coerce")

    p=partners.copy()
    p["馬番_num"]=pd.to_numeric(p["馬番"],errors="coerce")
    sim_top=set(p.sort_values(["Partner Score","MC複勝率"],ascending=False).head(3)["馬番_num"].dropna().astype(int))
    x["展開穴"]=x["馬番_num"].fillna(-1).astype(int).isin(sim_top)
    x["調教コース"]=x.get("course_badge",x.get("コース判定",False)).astype(bool)
    x["M適合"]=x.get("M評価",pd.Series("－",index=x.index)).astype(str).isin(["◎","○"])
    x["展開×調教穴"]=x["展開穴"] & x["調教コース"] & x["地雷_effective"].eq(0)
    x["展開×M穴"]=x["展開穴"] & x["M適合"]

    main=x[(x["地雷_effective"]==0)&x["人気_live"].notna()].sort_values(["人気_live","単勝_live"]).head(3)
    chosen=[]
    for _,r in main.iterrows():
        chosen.append((r,"本線相手","人気上位・地雷なし"))

    holes=x[x["展開穴"]].copy()
    holes["hole_priority"]=3*holes["展開×調教穴"].astype(int)+2*holes["展開×M穴"].astype(int)+holes["展開穴"].astype(int)
    score_map=dict(zip(p["馬番_num"],p["Partner Score"]))
    holes["Partner Score"]=holes["馬番_num"].map(score_map).fillna(0)
    holes=holes.sort_values(["hole_priority","Partner Score"],ascending=False)

    used={int(r["馬番_num"]) for r,_,_ in chosen if pd.notna(r["馬番_num"])}
    for _,r in holes.iterrows():
        no=int(r["馬番_num"]) if pd.notna(r["馬番_num"]) else -1
        if no in used: 
            continue
        if r["展開×調教穴"]:
            cat,reason="複合穴","展開◎ × 調教コース◎"
        elif r["展開×M穴"]:
            cat,reason="血統展開穴","展開◎ × M適合"
        else:
            cat,reason="展開穴","展開◎"
        chosen.append((r,cat,reason)); used.add(no)
        if len(chosen)>=max_total:
            break

    rows=[]
    for r,cat,reason in chosen[:max_total]:
        rows.append({
            "馬番":int(r["馬番_num"]) if pd.notna(r["馬番_num"]) else r.get("馬番"),
            "馬名":r.get("馬名",""),
            "区分":cat,
            "理由":reason,
            "人気":r.get("人気_live"),
            "単勝オッズ":r.get("単勝_live"),
            "展開":r.get("展開評価",""),
            "M":r.get("M評価","－"),
            "調教コース":bool(r.get("調教コース",False)),
        })
    return pd.DataFrame(rows)
