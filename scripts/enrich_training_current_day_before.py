from __future__ import annotations
import argparse, re
from pathlib import Path
import pandas as pd

def read_any(path):
    for enc in ("utf-8-sig","cp932","utf-8"):
        try:
            return pd.read_csv(path,encoding=enc,low_memory=False)
        except UnicodeDecodeError:
            pass
    return pd.read_csv(path,low_memory=False)

def hid(v):
    s=re.sub(r"\.0$","",str(v or "").strip())
    s=re.sub(r"[^0-9]","",s)
    return s[-8:] if len(s)>=8 else s

def dt(v):
    s=re.sub(r"\.0$","",str(v or "").strip())
    s=re.sub(r"[^0-9]","",s)
    if len(s)==6: s="20"+s
    return pd.to_datetime(s,format="%Y%m%d",errors="coerce")

def norm_surface(v):
    s=str(v or "").strip()
    if s.startswith("芝"): return "芝"
    if s.startswith("ダ"): return "ダ"
    return s

def norm_trainer(v):
    s=str(v or "").strip()
    aliases={"斉藤誠":"斎藤誠","加藤士津八":"加藤士津","加藤志津":"加藤士津"}
    for a,c in aliases.items():
        if s.startswith(a): return c
    return s

def col(df,names):
    for c in names:
        if c in df.columns: return c
    raise RuntimeError("missing column: "+"/".join(names))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--training",required=True)
    ap.add_argument("--hill",required=True)
    ap.add_argument("--master",required=True)
    a=ap.parse_args()

    tr=read_any(a.training)
    h=read_any(a.hill)
    m=read_any(a.master)

    tr_id=col(tr,["血統登録番号","繁殖登録番号"])
    h_id=col(h,["血統登録番号","繁殖登録番号"])
    h_date=col(h,["年月日","日付"])
    h_time=col(h,["Time1","TIME1"])

    tr["_hid"]=tr[tr_id].map(hid)
    tr["_race_dt"]=tr["年月日"].map(dt)
    tr["_prev_dt"]=tr["_race_dt"]-pd.Timedelta(days=1)

    h["_hid"]=h[h_id].map(hid)
    h["_date"]=h[h_date].map(dt)
    h["_time1"]=pd.to_numeric(h[h_time],errors="coerce")
    h=h[h["_hid"].ne("") & h["_date"].notna()].copy()

    counts=h.groupby(["_hid","_date"]).size().rename("前日坂路本数").reset_index()
    best=h.sort_values(["_hid","_date","_time1"],na_position="last").drop_duplicates(["_hid","_date"],keep="first")
    use=["_hid","_date","_time1"]
    if "時刻" in best.columns: use.append("時刻")
    best=best[use].merge(counts,on=["_hid","_date"],how="left")
    best=best.rename(columns={"_date":"_prev_dt","_time1":"前日坂路Time1","時刻":"前日坂路時刻"})

    for c in ["前日坂路あり","前日坂路Time1","前日坂路時刻","前日坂路本数","前日坂路調教日",
              "前日追いタイプ","前日追い正式採用","前日追い表示","前日追い備考","前日追い情報源"]:
        if c in tr.columns:
            tr=tr.drop(columns=[c])

    tr=tr.merge(best,on=["_hid","_prev_dt"],how="left")
    tr["前日坂路あり"]=tr["前日坂路Time1"].notna()
    tr["前日坂路調教日"]=tr["_prev_dt"].dt.strftime("%Y%m%d")
    tr.loc[~tr["前日坂路あり"],"前日坂路調教日"]=""
    tr["前日追い情報源"]="坂路raw×血統登録番号×実開催日前日"

    m["_trainer"]=m["調教師"].map(norm_trainer)
    m["_surface"]=m["芝ダ"].map(norm_surface)
    m["正式採用フラグ"]=pd.to_numeric(m["正式採用フラグ"],errors="coerce").fillna(0).astype(int)
    lookup=m.set_index(["_trainer","_surface"])

    tr["前日追いタイプ"]="NONE"
    tr["前日追い正式採用"]=False
    tr["前日追い表示"]=""
    tr["前日追い備考"]=""

    for i,r in tr[tr["前日坂路あり"]].iterrows():
        key=(norm_trainer(r.get("調教師","")),norm_surface(r.get("芝・ダ","")))
        if key not in lookup.index:
            tr.at[i,"前日追い表示"]="前日追いあり"
            continue
        rec=lookup.loc[key]
        if isinstance(rec,pd.DataFrame): rec=rec.iloc[0]
        formal=int(rec.get("正式採用フラグ",0))==1
        tr.at[i,"前日追いタイプ"]=str(rec.get("前日追いタイプ","NONE"))
        tr.at[i,"前日追い正式採用"]=formal
        tr.at[i,"前日追い表示"]=str(rec.get("表示ラベル","前日追いあり")) if formal else "前日追いあり"
        tr.at[i,"前日追い備考"]=str(rec.get("備考","") or "")

    tr=tr.drop(columns=["_hid","_race_dt","_prev_dt"],errors="ignore")
    tr.to_csv(a.training,index=False,encoding="utf-8-sig")
    print("rows",len(tr))
    print("day_before",int(tr["前日坂路あり"].sum()))
    print("formal",int(tr["前日追い正式採用"].sum()))

if __name__=="__main__":
    main()
