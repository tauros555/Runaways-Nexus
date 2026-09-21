from __future__ import annotations
from pathlib import Path
from datetime import datetime
import re, unicodedata
import pandas as pd

BASE=Path(__file__).resolve().parents[1]
M_DIR=BASE/'data'/'nexus_m'
SIRE_FILE=M_DIR/'m_sire_master.csv'; RUNNER_FILE=M_DIR/'m_runner_9branch.csv'; LINEAGE_FILE=M_DIR/'m_lineage_connection.csv'
GENERATED_FILE=M_DIR/'generated_runner_m.csv'; QUEUE_FILE=M_DIR/'m_completion_queue.csv'
BRANCH_COLS=['枝1_父ブロック_父父','枝2_父ブロック_母父','枝3_父ブロック_母母父','枝4_母父ブロック_父父','枝5_母父ブロック_母父','枝6_母父ブロック_母母父','枝7_母母父ブロック_父父','枝8_母母父ブロック_母父','枝9_母母父ブロック_母母父']

def _read(path):
    p=Path(path)
    if not p.exists(): return pd.DataFrame()
    for enc in ('utf-8-sig','cp932','utf-8'):
        try:return pd.read_csv(p,encoding=enc,low_memory=False)
        except Exception:pass
    return pd.DataFrame()

def _norm(v):
    if v is None:return ''
    try:
        if pd.isna(v):return ''
    except Exception:pass
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(v)).strip())

def _hid(v): return re.sub(r'\.0$','',_norm(v))

def _pick(row,names):
    for c in names:
        if c in row.index:
            v=_norm(row.get(c))
            if v and v.lower() not in {'nan','none','<na>','0'}: return v
    return ''

def _lineage_lookup():
    z=_read(LINEAGE_FILE); out={}
    if z.empty:return out
    for _,r in z.iterrows():
        h=_hid(r.get('血統登録番号'))
        if h: out[h]={'父':_pick(r,['父_正規名','父馬名']),'母父':_pick(r,['母父_正規名','母父馬名']),'母母父':_pick(r,['母母父_正規名','母母父馬名'])}
    return out

def _sire_index():
    s=_read(SIRE_FILE); d={}
    if s.empty:return s,d
    for idx,r in s.iterrows():
        for c in ['正規名','種牡馬名']:
            n=_norm(r.get(c))
            if n:d.setdefault(n,idx)
    return s,d

def _existing_ids():
    ids=set()
    for p in [RUNNER_FILE,GENERATED_FILE]:
        z=_read(p)
        if '血統登録番号' in z.columns: ids.update(_hid(v) for v in z['血統登録番号'] if _hid(v))
    return ids

def _lineage(row,fallback):
    h=_hid(row.get('血統登録番号')); fb=fallback.get(h,{})
    return (_pick(row,['父正規名','父','父馬名']) or fb.get('父',''),_pick(row,['母父正規名','母父','母父馬名']) or fb.get('母父',''),_pick(row,['母母父正規名','母母父','母母父馬名']) or fb.get('母母父',''))

def _build(row,f,mg,sd,sf,sm,ss):
    vals=[sf['父_父M'],sf['父_母父M'],sf['父_母母父M'],sm['父_父M'],sm['父_母父M'],sm['父_母母父M'],ss['父_父M'],ss['父_母父M'],ss['父_母母父M']]
    d={'血統登録番号':_hid(row.get('血統登録番号')),'馬名':_pick(row,['馬名']),'父正規名':_norm(sf.get('正規名',f)) or f,'母父正規名':_norm(sm.get('正規名',mg)) or mg,'母母父正規名':_norm(ss.get('正規名',sd)) or sd,'現代馬9枝シグネチャ':''.join(str(v) for v in vals),'M生成状態':'自動生成済','生成日時':datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    d.update(dict(zip(BRANCH_COLS,vals))); return d

def ensure_current_horses(current):
    sire,idx=_sire_index(); fallback=_lineage_lookup(); existing=_existing_ids(); generated=_read(GENERATED_FILE)
    generated_ids=set(_hid(v) for v in generated.get('血統登録番号',[])) if not generated.empty else set(); status=[]; new=[]; queue=[]
    for _,r in current.iterrows():
        h=_hid(r.get('血統登録番号')); name=_pick(r,['馬名'])
        if h and h in existing:
            src='自動生成済' if h in generated_ids else '既存M'; status.append({'血統登録番号':h,'馬番':r.get('馬番'),'馬名':name,'M付与状態':src,'M自動生成':False,'M補完待ち':False}); continue
        f,mg,sd=_lineage(r,fallback); miss=[]
        sf=sire.loc[idx[f]] if f in idx else None; sm=sire.loc[idx[mg]] if mg in idx else None; ss=sire.loc[idx[sd]] if sd in idx else None
        if not f: miss.append('父名')
        elif sf is None: miss.append(f'父M:{f}')
        if not mg: miss.append('母父名')
        elif sm is None: miss.append(f'母父M:{mg}')
        if not sd: miss.append('母母父名')
        elif ss is None: miss.append(f'母母父M:{sd}')
        if not miss:
            new.append(_build(r,f,mg,sd,sf,sm,ss)); status.append({'血統登録番号':h,'馬番':r.get('馬番'),'馬名':name,'M付与状態':'自動生成済','M自動生成':True,'M補完待ち':False})
        else:
            queue.append({'血統登録番号':h,'馬名':name,'父':f,'母父':mg,'母母父':sd,'不足項目':' / '.join(miss),'状態':'補完待ち','検出日時':datetime.now().strftime('%Y-%m-%d %H:%M:%S')}); status.append({'血統登録番号':h,'馬番':r.get('馬番'),'馬名':name,'M付与状態':'M未付与','M自動生成':False,'M補完待ち':True})
    new_df=pd.DataFrame(new)
    if new:
        z=pd.concat([generated,new_df],ignore_index=True,sort=False) if not generated.empty else new_df.copy(); z=z.drop_duplicates('血統登録番号',keep='last')
        try: z.to_csv(GENERATED_FILE,index=False,encoding='utf-8-sig')
        except OSError: pass
    q=pd.DataFrame(queue)
    try: q.to_csv(QUEUE_FILE,index=False,encoding='utf-8-sig')
    except OSError: pass
    return pd.DataFrame(status),q,new_df

def combined_runner_master():
    b=_read(RUNNER_FILE); g=_read(GENERATED_FILE)
    if g.empty:return b
    if b.empty:return g
    return pd.concat([b,g],ignore_index=True,sort=False).drop_duplicates('血統登録番号',keep='last')
