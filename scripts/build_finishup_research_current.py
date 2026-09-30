"""Generate the separate 0–7 trainer finishing research display at update time."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from modules.finishup_research import features,score,hydrate_missing_workouts
from modules.trainer_rules_v26 import apply_trainer_rules,formal_trainer_rule,norm,NEW_SURFACE_TRAINERS
from scripts.update_history_seed import RACE_HEADERS

def read_any(path,**kw):
    for enc in ('utf-8-sig','cp932','utf-8'):
        try:return pd.read_csv(path,encoding=enc,low_memory=False,**kw)
        except UnicodeDecodeError:pass
    raise ValueError(f'CSVを読めません: {path}')

def main():
    a=argparse.ArgumentParser()
    for name in ['training','hill','wood','model','out']:a.add_argument('--'+name,required=True,type=Path)
    a.add_argument('--race',type=Path)
    opt=a.parse_args()
    training=read_any(opt.training,dtype=str)
    # Match the app's official judgment on the exported CSV.  Reconstructed
    # clocks may feed the research model, but must not silently change ○.
    training['_formal_trainer_ok']=apply_trainer_rules(training)['調教師判定_正式'].astype(bool)
    hill=read_any(opt.hill,dtype=str)
    wood=read_any(opt.wood,dtype=str)
    hill_required={'血統登録番号','調教師','年月日','Time1','Lap1','Lap2','Lap3','Lap4'}
    if not hill_required.issubset(hill):raise ValueError('h.csvに不足列: '+str(sorted(hill_required-set(hill))))
    required={'血統登録番号','調教師','年月日','5F','4F','Lap1','Lap2'}
    if not required.issubset(wood):raise ValueError('w.csvに不足列: '+str(sorted(required-set(wood))))
    race=pd.DataFrame(columns=['年月日','場所','R','クラスコード'])
    if opt.race and opt.race.exists():
        race=read_any(opt.race,dtype=str,header=None)
        if race.shape[1]!=len(RACE_HEADERS):raise ValueError(f'レースデータの列数: {race.shape[1]} / 想定: {len(RACE_HEADERS)}')
        race.columns=RACE_HEADERS
        yy=pd.to_numeric(race['年'],errors='coerce');yy=yy.where(yy>=1000,yy+2000)
        mm=pd.to_numeric(race['月'],errors='coerce');dd=pd.to_numeric(race['日'],errors='coerce')
        race['年月日']=(yy*10000+mm*100+dd).astype('Int64').astype(str)
    training=hydrate_missing_workouts(training,hill,wood)
    # The three new surface-specific rules must see the same dated h.csv clock
    # when Excel exported "なし".  Preserve all other formal judgments from CSV.
    selected=training['調教師'].map(norm).isin(NEW_SURFACE_TRAINERS)
    training['_new_trainer_condition']=False
    if selected.any():
        training.loc[selected,'_new_trainer_condition']=training.loc[selected].apply(formal_trainer_rule,axis=1).astype(bool)
        training.loc[selected,'_formal_trainer_ok']=training.loc[selected,'_new_trainer_condition']
    x=features(training,wood,race)
    out=score(x,opt.model)
    opt.out.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(opt.out,index=False,encoding='utf-8-sig')
    print('研究指数',len(out),'算出',int(out.status.eq('算出').sum()),'B1',int(out['B1警告'].sum()))
    print('未算出内訳',out.loc[out.status.ne('算出'),'status'].value_counts().to_dict())

if __name__=='__main__':main()
