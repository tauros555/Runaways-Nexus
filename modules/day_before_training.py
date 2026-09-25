from __future__ import annotations
from pathlib import Path
import pandas as pd
BASE=Path(__file__).resolve().parents[1]
DEFAULT_EFFECT_MASTER=BASE/'data'/'day_before_training_effect_master.csv'
DEFAULT_CURRENT=BASE/'data'/'day_before_training_current.csv'
DISPLAY_BY_TYPE={'WIN':'単🔥 前日追い【勝率↑】','PLACE':'複・紐 前日追い【複勝↑】','BOTH':'軸・単🔥 前日追い【勝率・複勝↑】'}

def _read_csv(path):
    p=Path(path)
    if not p.exists(): return pd.DataFrame()
    for enc in ('utf-8-sig','cp932','utf-8'):
        try: return pd.read_csv(p,encoding=enc,low_memory=False)
        except UnicodeDecodeError: pass
    return pd.read_csv(p,low_memory=False)

def _norm_surface(v):
    s=str(v or '').strip()
    if s.startswith('ダ'): return 'ダ'
    if s.startswith('芝'): return '芝'
    return s

def _norm_trainer(v):
    s=str(v or '').strip()
    aliases={'斉藤誠':'斎藤誠','加藤士津八':'加藤士津','加藤志津':'加藤士津'}
    for a,c in aliases.items():
        if s.startswith(a): return c
    return s

def load_day_before_bundle(current_path=DEFAULT_CURRENT,effect_master_path=DEFAULT_EFFECT_MASTER):
    current=_read_csv(current_path); master=_read_csv(effect_master_path)
    if not master.empty:
        master=master.copy(); master['調教師_key']=master['調教師'].map(_norm_trainer); master['芝ダ_key']=master['芝ダ'].map(_norm_surface)
        master['正式採用フラグ']=pd.to_numeric(master['正式採用フラグ'],errors='coerce').fillna(0).astype(int)
    return current,master

def attach_day_before_training(race_df,current,effect_master):
    out=race_df.copy()
    if out.empty: return out
    for c,v in [('前日坂路あり',False),('前日坂路Time1',pd.NA),('前日追いタイプ','NONE'),('前日追い正式採用',False),('前日追い表示',''),('前日追い備考','')]:
        if c not in out.columns: out[c]=v
    if current is None or current.empty: return out
    c=current.copy()
    for k in ('年月日','R','馬番'):
        if k in c.columns: c[k]=pd.to_numeric(c[k],errors='coerce').astype('Int64')
        if k in out.columns: out[k]=pd.to_numeric(out[k],errors='coerce').astype('Int64')
    keys=[k for k in ('年月日','場所','R','馬番') if k in c.columns and k in out.columns]
    use=[x for x in ['前日坂路あり','前日坂路Time1','前日坂路調教日','前日坂路本数','前日坂路時刻'] if x in c.columns]
    out=out.drop(columns=[x for x in use if x in out.columns],errors='ignore').merge(c[keys+use].drop_duplicates(keys,keep='last'),on=keys,how='left')
    out['前日坂路あり']=out.get('前日坂路あり',False).fillna(False).astype(bool)
    out['前日追いタイプ']='NONE'; out['前日追い正式採用']=False; out['前日追い表示']=''; out['前日追い備考']=''
    if effect_master is None or effect_master.empty:
        out.loc[out['前日坂路あり'],'前日追い表示']='前日追いあり'; return out
    m=effect_master.copy()
    if '調教師_key' not in m: m['調教師_key']=m['調教師'].map(_norm_trainer)
    if '芝ダ_key' not in m: m['芝ダ_key']=m['芝ダ'].map(_norm_surface)
    lookup=m.set_index(['調教師_key','芝ダ_key'],drop=False)
    out['_trainer_key']=out.get('調教師',pd.Series('',index=out.index)).map(_norm_trainer)
    out['_surface_key']=out.get('芝・ダ',pd.Series('',index=out.index)).map(_norm_surface)
    for idx,row in out[out['前日坂路あり']].iterrows():
        key=(row['_trainer_key'],row['_surface_key'])
        if key not in lookup.index:
            out.at[idx,'前日追い表示']='前日追いあり'; continue
        rec=lookup.loc[key]
        if isinstance(rec,pd.DataFrame): rec=rec.iloc[0]
        formal=int(pd.to_numeric(rec.get('正式採用フラグ',0),errors='coerce') or 0)==1
        typ=str(rec.get('前日追いタイプ','NONE') or 'NONE').strip().upper()
        out.at[idx,'前日追いタイプ']=typ; out.at[idx,'前日追い正式採用']=formal; out.at[idx,'前日追い備考']=str(rec.get('備考','') or '')
        out.at[idx,'前日追い表示']=(str(rec.get('表示ラベル','') or '').strip() or DISPLAY_BY_TYPE.get(typ,'前日追いあり')) if formal else '前日追いあり'
    return out.drop(columns=['_trainer_key','_surface_key'],errors='ignore')
