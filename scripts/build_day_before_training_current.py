from __future__ import annotations
import argparse,io,re
from pathlib import Path
import pandas as pd

def read_csv_any(path):
    for enc in ('utf-8-sig','cp932','utf-8'):
        try:return pd.read_csv(path,encoding=enc,low_memory=False)
        except UnicodeDecodeError:pass
    return pd.read_csv(path,low_memory=False)

def read_hill(path):
    try:
        return read_csv_any(path)
    except UnicodeDecodeError:
        pass
    # TARGET may end this horse's half-width name with a lone CP932 lead
    # byte. Repair that field in memory while leaving the source CSV intact.
    original=Path(path).read_bytes()
    repaired=[]
    count=0
    for row in original.splitlines(keepends=True):
        if row.startswith(b'2024106565,'):
            fields=row.split(b',',6)
            if len(fields)==7 and fields[5].endswith(b'\x82'):
                fields[5]=fields[5][:-1]
                row=b','.join(fields)
                count+=1
        repaired.append(row)
    if count==0 or original.decode('cp932',errors='replace').count('\ufffd')!=count:
        raise ValueError(f'CSVを読めません: {path}（既知の馬名末尾以外に破損があります）')
    fixed=b''.join(repaired)
    fixed.decode('cp932')
    print(f'h.csv: 馬名末尾の不完全な文字 {count} 件を読み込み時に補正')
    return pd.read_csv(io.BytesIO(fixed),encoding='cp932',low_memory=False)

def hid(v):
    s=re.sub(r'\.0$','',str(v).strip()); s=re.sub(r'[^0-9]','',s)
    return s[-8:] if len(s)>=8 else s

def ymd(v):
    s=re.sub(r'\.0$','',str(v).strip()); s=re.sub(r'[^0-9]','',s)
    if len(s)==6:s='20'+s
    return pd.to_datetime(s,format='%Y%m%d',errors='coerce')

def col(df,names,required=True):
    for c in names:
        if c in df.columns:return c
    if required:raise RuntimeError('必要列がありません: '+str(names))
    return None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--training',required=True,type=Path); ap.add_argument('--hill',required=True,type=Path); ap.add_argument('--out',required=True,type=Path); a=ap.parse_args()
    race=read_csv_any(a.training); hill=read_hill(a.hill)
    rid=col(race,['血統登録番号','繁殖登録番号']); hidc=col(hill,['血統登録番号','繁殖登録番号']); hdate=col(hill,['年月日','日付']); htime=col(hill,['Time1','TIME1']); hclock=col(hill,['時刻'],False)
    race=race.copy(); hill=hill.copy(); race['_hid']=race[rid].map(hid); race['_race_date']=race['年月日'].map(ymd); race['_prev_date']=race['_race_date']-pd.Timedelta(days=1)
    hill['_hid']=hill[hidc].map(hid); hill['_date']=hill[hdate].map(ymd); hill['_time1']=pd.to_numeric(hill[htime],errors='coerce')
    hill=hill.sort_values(['_hid','_date','_time1'],na_position='last')
    cnt=hill.groupby(['_hid','_date'],dropna=False).size().rename('前日坂路本数').reset_index(); best=hill.drop_duplicates(['_hid','_date'],keep='first').merge(cnt,on=['_hid','_date'],how='left')
    keep=['_hid','_date','_time1','前日坂路本数']+([hclock] if hclock else []); best=best[keep].rename(columns={'_date':'_prev_date','_time1':'前日坂路Time1',hclock:'前日坂路時刻' if hclock else hclock})
    keys=[c for c in ['年月日','場所','R','馬番','馬名','調教師','芝・ダ','血統登録番号'] if c in race.columns]
    out=race[keys+['_hid','_prev_date']].merge(best,on=['_hid','_prev_date'],how='left'); out['前日坂路あり']=out['前日坂路Time1'].notna(); out['前日坂路調教日']=out['_prev_date'].dt.strftime('%Y%m%d'); out.loc[~out['前日坂路あり'],'前日坂路調教日']=''; out=out.drop(columns=['_hid','_prev_date'])
    a.out.parent.mkdir(parents=True,exist_ok=True); out.to_csv(a.out,index=False,encoding='utf-8-sig'); print(f'rows={len(out):,}'); print(f'day_before_hill={int(out["前日坂路あり"].sum()):,}'); print(a.out)
if __name__=='__main__':main()

