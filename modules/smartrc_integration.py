from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
SMART_RC_FILE = BASE / "data" / "rd" / "smartrc_ten_latest.csv"
SMART_RC_WEIGHT = 0.30

PLACE_CODE = {
    "札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05",
    "中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10",
}

def _read_csv(path:Path) -> pd.DataFrame:
    last=None
    for enc in ("utf-8-sig","cp932","utf-8"):
        try:
            return pd.read_csv(path,encoding=enc,low_memory=False,dtype={"rcode":"string"})
        except Exception as e:
            last=e
    raise RuntimeError(f"SmartRC CSVを読み込めません: {last}")

def load_smartrc(path:Path=SMART_RC_FILE) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    x=_read_csv(path)
    if "rcode" not in x.columns or "馬番" not in x.columns:
        raise ValueError("SmartRC CSVに rcode / 馬番 がありません。")
    x["rcode"]=x["rcode"].astype("string").str.replace(r"\.0$","",regex=True).str.zfill(16)
    x["馬番"]=pd.to_numeric(x["馬番"],errors="coerce").astype("Int64")
    if "ten_has" in x.columns:
        x["ten_has"]=pd.to_numeric(x["ten_has"],errors="coerce")
    else:
        x["ten_has"]=np.nan
    x["_date"]=pd.to_datetime(x["rcode"].str.slice(0,8),format="%Y%m%d",errors="coerce")
    x["_place_code"]=x["rcode"].str.slice(8,10)
    x["_R"]=pd.to_numeric(x["rcode"].str.slice(14,16),errors="coerce").astype("Int64")
    return x

def select_race_smartrc(x:pd.DataFrame,date_value,place,race_no) -> pd.DataFrame:
    if x is None or x.empty:
        return pd.DataFrame()
    try:
        d=pd.to_datetime(str(int(date_value)),format="%Y%m%d",errors="coerce")
    except Exception:
        d=pd.NaT
    pc=PLACE_CODE.get(str(place),"")
    r=int(race_no)
    z=x[
        (x["_date"]==d)
        &(x["_place_code"].astype(str)==pc)
        &(x["_R"]==r)
    ].copy()
    if z.empty:
        return z
    return z.sort_values("馬番").drop_duplicates(["馬番"],keep="last")

def _z(s:pd.Series, reverse=False) -> pd.Series:
    v=pd.to_numeric(s,errors="coerce")
    mu=v.mean()
    sd=v.std(ddof=0)
    if pd.isna(sd) or sd < 1e-9:
        z=pd.Series(0.0,index=v.index)
    else:
        z=(v-mu)/sd
    return -z if reverse else z

def integrate_ten(pred:pd.DataFrame, smart_race:pd.DataFrame, weight:float=SMART_RC_WEIGHT):
    """
    Formal SmartRC integration v1.

    RDテン:
      StartDash 45% + EarlyTracking 35% + LeadProb 20%

    SmartRC:
      ten_has (smaller = faster)

    Both are race-standardized, then:
      IntegratedTenZ = 70% RD + 30% SmartRC

    If SmartRC is missing for a horse, that horse uses RD 100%.
    This changes the "テン争い" interpretation/ranking only.
    It does NOT directly add points to FullWinProb or Runaway's Ver7 score.
    """
    x=pred.copy()
    for c,d in [("StartDashScore",50.0),("EarlyTrackingScore",50.0),("LeadProb_Jockey",0.08)]:
        if c not in x.columns: x[c]=d
        x[c]=pd.to_numeric(x[c],errors="coerce").fillna(d)

    x["RDテンRaw"]=(0.45*x["StartDashScore"]+0.35*x["EarlyTrackingScore"]+0.20*(x["LeadProb_Jockey"].clip(0,1)*100))
    x["RDテンZ"]=_z(x["RDテンRaw"])

    if smart_race is None or smart_race.empty:
        x["SmartRC_ten_has"]=np.nan
        x["SmartRCテンZ"]=np.nan
        x["SmartRC反映"]=False
        x["統合テンZ"]=x["RDテンZ"]
        x["統合テン順位"]=x["統合テンZ"].rank(method="first",ascending=False).astype(int)
        return x, {"status":"NO_RACE_DATA","matched":0,"total":len(x),"weight":weight}

    s=smart_race[[c for c in ["馬番","ten_has","ten_has_rank","馬名","SmartRC馬コード","rcode"] if c in smart_race.columns]].copy()
    rename={"ten_has":"SmartRC_ten_has","ten_has_rank":"SmartRC_ten_has_rank","馬名":"SmartRC馬名"}
    s=s.rename(columns=rename)
    x["馬番"]=pd.to_numeric(x["馬番"],errors="coerce").astype("Int64")
    x=x.merge(s,on="馬番",how="left")

    x["SmartRCテンZ"]=_z(x["SmartRC_ten_has"],reverse=True)
    avail=x["SmartRC_ten_has"].notna()
    x["SmartRC反映"]=avail

    # Horse-level fallback: missing SmartRC => RD 100%
    x["統合テンZ"]=x["RDテンZ"]
    x.loc[avail,"統合テンZ"]=(1-weight)*x.loc[avail,"RDテンZ"]+weight*x.loc[avail,"SmartRCテンZ"]
    x["統合テン順位"]=x["統合テンZ"].rank(method="first",ascending=False).astype(int)

    # 0-100 display score from within-race normal CDF-like scaling.
    # Ranking analysis uses Z; this column is display-only.
    z=x["統合テンZ"].clip(-3,3)
    x["統合テン指数"]=(50+15*z).clip(0,100)

    return x,{
        "status":"OK",
        "matched":int(avail.sum()),
        "total":len(x),
        "weight":weight,
        "rcode":str(smart_race["rcode"].iloc[0]) if "rcode" in smart_race.columns and len(smart_race) else "",
    }
