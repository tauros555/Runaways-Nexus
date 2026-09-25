from __future__ import annotations
from pathlib import Path
from datetime import datetime
import shutil
import pandas as pd

BASE=Path(__file__).resolve().parents[1]
DATASETS={
    '出馬表・調教データ': BASE/'data'/'training_current.csv',
    'A3履歴': BASE/'data'/'a3_history.csv',
    '前日追い判定': BASE/'data'/'day_before_training_current.csv',
    '前日追い効果マスタ': BASE/'data'/'day_before_training_effect_master.csv',
    '過去走データ': BASE/'data'/'rd'/'history_seed_2020_2026.csv.gz',
    'M出走馬マスタ': BASE/'data'/'nexus_m'/'m_runner_9branch.csv',
    'M種牡馬マスタ': BASE/'data'/'nexus_m'/'m_sire_master.csv',
}
INBOX=BASE/'data'/'inbox'

def file_signature(path):
    p=Path(path)
    if not p.exists(): return 'missing'
    st=p.stat(); return f'{st.st_mtime_ns}:{st.st_size}'

def dataset_signature():
    return '|'.join(f'{k}={file_signature(v)}' for k,v in DATASETS.items())

def dataset_status():
    now=datetime.now(); rows=[]
    for name,p in DATASETS.items():
        if p.exists():
            m=datetime.fromtimestamp(p.stat().st_mtime); age=(now-m).total_seconds()/3600
            rows.append({'データ':name,'状態':'OK','更新日時':m.strftime('%Y/%m/%d %H:%M:%S'),'経過時間':f'{age:.1f}h','サイズMB':round(p.stat().st_size/1024/1024,2)})
        else:
            rows.append({'データ':name,'状態':'MISSING','更新日時':'-','経過時間':'-','サイズMB':0})
    return pd.DataFrame(rows)

def sync_inbox():
    INBOX.mkdir(parents=True,exist_ok=True)
    mapping={
        'training_current.csv':DATASETS['出馬表・調教データ'],
        'a3_history.csv':DATASETS['A3履歴'],
        'history_seed_2020_2026.csv.gz':DATASETS['過去走データ'],
    }
    msgs=[]
    for fn,dst in mapping.items():
        src=INBOX/fn
        if not src.exists(): continue
        if (not dst.exists()) or src.stat().st_mtime_ns>dst.stat().st_mtime_ns:
            dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); msgs.append(f'{fn}: 取込完了')
        else: msgs.append(f'{fn}: 更新なし')
    return msgs
