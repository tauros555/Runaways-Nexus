"""Pre-race research index.  Kept separate from Nexus probabilities and crowns."""
from __future__ import annotations

from pathlib import Path
import json
import re
import unicodedata
import numpy as np
import pandas as pd
from modules.trainer_rules_v26 import apply_trainer_rules

GRADE = {7:'未勝利',15:'未勝利',23:'条件戦',43:'条件戦',67:'条件戦',
         115:'オープン',131:'オープン',147:'重賞',163:'重賞',179:'重賞',195:'重賞'}

def race_name_grade(value):
    """Fallback only when the separate race CSV has no matching current race."""
    name=unicodedata.normalize('NFKC',str(value or '')).upper().replace(' ','')
    if re.search(r'障害|ジャンプ|ジャン|ジャ',name):return '障害'
    if '新馬' in name or '未勝利' in name:return '未勝利'
    if re.search(r'G[123]|G[ⅠⅡⅢ]|GⅠ|GⅡ|GⅢ',name):return '重賞'
    if re.search(r'[123]勝',name):return '条件戦'
    if re.search(r'オープン|リステッド|OP|L$|S$',name):return 'オープン'
    return 'その他'

def num(s): return pd.to_numeric(s,errors='coerce')
def clock(s,bins,labels):
    return pd.cut(s,bins,right=False,labels=labels).astype(str).replace('nan','なし')
def col(frame,name):
    return num(frame[name]) if name in frame else pd.Series(np.nan,index=frame.index)
def chosen(values,flags):
    a=np.column_stack([np.asarray(f,dtype=bool) for f in flags])
    return np.where(a.any(axis=1),np.array(values)[a.argmax(axis=1)],'none')

def hydrate_missing_workouts(training:pd.DataFrame,hill:pd.DataFrame,wood:pd.DataFrame)->pd.DataFrame:
    """Fill missing Excel-exported clocks from the same dated TARGET h/w records.

    The exported CSV wins whenever it contains a valid numeric clock.  Exact
    horse, trainer and day matches prevent a preceding race's work leaking in.
    """
    t=training.copy().reset_index(drop=True)
    dates=pd.to_datetime(t['年月日'].astype(str).str.replace(r'\.0$','',regex=True),format='%Y%m%d',errors='coerce')
    week=dates-pd.to_timedelta(dates.dt.weekday,unit='D')
    week=week.where(~dates.dt.weekday.le(1),week-pd.Timedelta(days=7))
    horse=t['血統登録番号'].astype(str).str.replace(r'\.0$','',regex=True).str.replace(r'\D','',regex=True).str[-8:]
    trainer=t['調教師'].astype(str).str.strip()
    recovered=pd.Series(False,index=t.index)

    def lookup(raw,clock,columns,lo,hi):
        v=raw.copy()
        v['_horse']=v['血統登録番号'].astype(str).str.replace(r'\.0$','',regex=True).str.replace(r'\D','',regex=True).str[-8:]
        v['_trainer']=v['調教師'].astype(str).str.strip()
        v['_day']=pd.to_datetime(v['年月日'].astype(str),format='%Y%m%d',errors='coerce')
        for c in columns:v[c]=pd.to_numeric(v[c],errors='coerce')
        v=v[v[clock].between(lo,hi)].sort_values(clock,kind='stable')
        v=v.drop_duplicates(['_horse','_trainer','_day'])
        return {(r['_horse'],r['_trainer'],r['_day']):r for r in v.to_dict('records')}

    h=lookup(hill,'Time1',['Time1','Lap1','Lap2','Lap3','Lap4'],35,130)
    # For wood 4F-only workouts a 5F clock is not required.  Prefer 5F work
    # when present, then the fastest whole clock within that kind.
    w=wood.copy()
    for c in ['5F','4F','1F','Lap1','Lap2']:w[c]=pd.to_numeric(w[c],errors='coerce')
    w['5F']=w['5F'].where(w['5F'].between(55,100))
    w['4F']=w['4F'].where(w['4F'].between(40,90))
    w['_whole']=w['5F'].fillna(w['4F']+50)
    w=w[w['5F'].notna()|w['4F'].notna()]
    w['_horse']=w['血統登録番号'].astype(str).str.replace(r'\.0$','',regex=True).str.replace(r'\D','',regex=True).str[-8:]
    w['_trainer']=w['調教師'].astype(str).str.strip()
    w['_day']=pd.to_datetime(w['年月日'].astype(str),format='%Y%m%d',errors='coerce')
    w=w.sort_values('_whole',kind='stable').drop_duplicates(['_horse','_trainer','_day'])
    wd={(r['_horse'],r['_trainer'],r['_day']):r for r in w.to_dict('records')}

    def fill(row,col,value):
        if col in t and pd.isna(pd.to_numeric(t.at[row,col],errors='coerce')) and pd.notna(value):
            t.at[row,col]=value
            recovered.iloc[row]=True

    for i in range(len(t)):
        if pd.isna(dates.iloc[i]):continue
        root=(horse.iloc[i],trainer.iloc[i])
        days=[('坂1w前 土',week.iloc[i]-pd.Timedelta(days=2)),
              ('坂1w前 日',week.iloc[i]-pd.Timedelta(days=1)),
              (' 坂 水',week.iloc[i]+pd.Timedelta(days=2)),
              (' 坂 木',week.iloc[i]+pd.Timedelta(days=3)),
              (' 坂 前日',dates.iloc[i]-pd.Timedelta(days=1))]
        for prefix,day in days:
            r=h.get((*root,day))
            if r is None:continue
            fill(i,prefix+' TIME1',r['Time1'])
            if prefix!=' 坂 前日':
                for lap in ['Lap1','Lap2','Lap3','Lap4']:
                    col=prefix+' '+lap.upper()
                    fill(i,col,r[lap])
        for prefix,day in [('ウ1w前 土',week.iloc[i]-pd.Timedelta(days=2)),
                           ('ウ1w前 日',week.iloc[i]-pd.Timedelta(days=1)),
                           ('ウ 水',week.iloc[i]+pd.Timedelta(days=2)),
                           ('ウ 木',week.iloc[i]+pd.Timedelta(days=3))]:
            r=wd.get((*root,day))
            if r is None:continue
            if prefix.startswith('ウ1w前'):
                fill(i,prefix+' 5F',r['5F'])
                fill(i,prefix+' １F',r['1F'])
            else:
                for label,attr in [('5F','_5F'),('4F','_4F'),('1F','_1F')]:
                    fill(i,prefix+' '+label,r[label])
    t['_source_recovered']=recovered
    return t

def features(t:pd.DataFrame,wood:pd.DataFrame,races:pd.DataFrame)->pd.DataFrame:
    """Rebuild the training-time feature definitions from the current card and raw wood."""
    x=t.copy().reset_index(drop=True)
    x['_date']=pd.to_datetime(x['年月日'].astype(str).str.replace(r'\.0$','',regex=True),format='%Y%m%d',errors='coerce')
    x['_horse']=x['血統登録番号'].astype(str).str.replace(r'\.0$','',regex=True).str.replace(r'\D','',regex=True).str[-8:]
    x['_trainer']=x['調教師'].astype(str).str.strip()
    x['_week']=x._date-pd.to_timedelta(x._date.dt.weekday,unit='D')
    x.loc[x._date.dt.weekday.le(1),'_week']-=pd.Timedelta(days=7)
    x['surface']=x['芝・ダ'].astype(str).str.strip().str[0]
    x['weekday']=x._date.dt.weekday
    x['grade_code']=np.nan
    rk=races.copy()
    rk['_date']=pd.to_datetime(rk['年月日'].astype(str),format='%Y%m%d',errors='coerce')
    rk['_place']=rk['場所'].astype(str).str.strip()
    rk['_r']=num(rk['R'])
    rk=rk[['_date','_place','_r','クラスコード']].drop_duplicates(['_date','_place','_r'],keep='last')
    x['_place']=x['場所'].astype(str).str.strip();x['_r']=num(x['R'])
    x=x.merge(rk,on=['_date','_place','_r'],how='left',validate='many_to_one')
    x['grade']=num(x['クラスコード']).map(GRADE)
    fallback=x['レース名'].map(race_name_grade)
    x['grade']=x['grade'].fillna(fallback)

    # Workbook fields contain the fastest work on each Wednesday/Thursday.
    hw,ht=col(x,' 坂 水 TIME1'),col(x,' 坂 木 TIME1')
    hw=hw.where(hw.between(35,130));ht=ht.where(ht.between(35,130))
    l1w,l2w,l1t,l2t=[col(x,c) for c in (' 坂 水 LAP1',' 坂 水 LAP2',' 坂 木 LAP1',' 坂 木 LAP2')]
    validw,validt=hw.notna(),ht.notna()
    x['hill_fast']=pd.concat([hw,ht],axis=1).min(axis=1)
    x['hill_end_13']=((l1w.ge(13)&validw)|(l1t.ge(13)&validt))
    x['hill_accel_05']=(((l2w>l1w)&(l2w-l1w).le(.5)&validw)|((l2t>l1t)&(l2t-l1t).le(.5)&validt))
    hillflags=[]
    for name,fun in [
        ('A3',lambda a,b:(a>b)&b.le(12)),('A2',lambda a,b:(a>b)&b.gt(12)&b.lt(13)&a.ge(12)&a.lt(13)),
        ('A1',lambda a,b:(a>b)&b.gt(12)&b.lt(13)&a.ge(13)),
        ('B3',lambda a,b:(b>a)&a.le(12)),('B2',lambda a,b:(b>a)&a.gt(12)&a.lt(13)&b.ge(12)&b.lt(13)),
        ('B1',lambda a,b:(b>a)&a.gt(12)&a.lt(13)&b.ge(13))]:
        x[name]=(fun(l2w,l1w)&validw)|(fun(l2t,l1t)&validt)
        hillflags.append(x[name])
    x['B1警告']=x['B1']
    x['hill_type']=chosen(['A3','A2','A1','B3','B2','B1'],hillflags)
    fastest_w=hw.fillna(np.inf).le(ht.fillna(np.inf))
    cl2=pd.Series(np.where(fastest_w,l2w,l2t),index=x.index).where(x.hill_fast.notna())
    cl1=pd.Series(np.where(fastest_w,l1w,l1t),index=x.index).where(x.hill_fast.notna())
    x['hill_delta_bin']=pd.cut((cl2-cl1).round(1),[-100,-.05,.05,.25,.55,.95,100],
                               labels=['減速','同じ','+0.1-0.2','+0.3-0.5','+0.6-0.9','+1.0以上']).astype(str).replace('nan','なし')
    x['hill_end_bin']=clock(cl1,[0,12.05,12.45,13,100],['<=12','12.1-12.4','12.5-12.9','13+'])
    x['prior_clock']=pd.concat([col(x,'坂1w前 土 TIME1'),col(x,'坂1w前 日 TIME1')],axis=1).min(axis=1)
    x['pre_clock']=col(x,' 坂 前日 TIME1')

    # Raw w.csv is required: the workbook export omits prior-weekend wood 4F
    # and weekday wood Lap2. Choose fastest whole clock per horse/day.
    w=wood.copy()
    for c in ['5F','4F','Lap1','Lap2']:w[c]=num(w[c])
    w['5F']=w['5F'].where(w['5F'].between(55,100))
    w['4F']=w['4F'].where(w['4F'].between(40,90))
    w=w[w['5F'].notna()|w['4F'].notna()].copy()
    w['_horse']=w['血統登録番号'].astype(str).str.replace(r'\.0$','',regex=True).str.replace(r'\D','',regex=True).str[-8:]
    w['_trainer']=w['調教師'].astype(str).str.strip()
    w['_day']=pd.to_datetime(w['年月日'].astype(str),format='%Y%m%d',errors='coerce')
    # A stale raw export must never turn real weekend wood into a false 'none'.
    earliest,latest=w._day.min(),w._day.max()
    x['_wood_complete']=(x._week-pd.Timedelta(days=2)).ge(earliest)&(x._week+pd.Timedelta(days=3)).le(latest)
    w['_clock']=w['5F'].fillna(w['4F'])
    w['_priority']=w['5F'].isna().astype(int)
    w=w.sort_values(['_priority','_clock'],kind='stable').drop_duplicates(['_horse','_trainer','_day'])
    base=w[['_horse','_trainer','_day','5F','4F','Lap1','Lap2']]
    for key,day in [('sat',x._week-pd.Timedelta(days=2)),('sun',x._week-pd.Timedelta(days=1)),
                    ('wed',x._week+pd.Timedelta(days=2)),('thu',x._week+pd.Timedelta(days=3))]:
        x['_day']=day
        q=base.rename(columns={c:key+'_'+c for c in ['5F','4F','Lap1','Lap2']})
        x=x.merge(q,on=['_horse','_trainer','_day'],how='left',validate='many_to_one').drop(columns='_day')
    known={'sat':'ウ1w前 土 5F','sun':'ウ1w前 日 5F','wed':'ウ 水 5F','thu':'ウ 木 5F'}
    for key,header in known.items():
        original=col(x,header)
        x['_wood_complete']&=original.isna()|(original-x[key+'_5F']).abs().le(.11)
    wh=[x[k+'_5F'] for k in ['wed','thu']]
    x['wood5']=pd.concat(wh,axis=1).min(axis=1)
    w4=[x[k+'_4F'].where(x[k+'_5F'].isna()) for k in ['wed','thu']]
    x['wood4']=pd.concat(w4,axis=1).min(axis=1)
    woodflags=[]
    for name,series in [('wood_end11_accel',((x.wed_Lap1.ge(11)&x.wed_Lap1.lt(12)&x.wed_Lap2.gt(x.wed_Lap1))|
                                                (x.thu_Lap1.ge(11)&x.thu_Lap1.lt(12)&x.thu_Lap2.gt(x.thu_Lap1)))),
                        ('wood_5F_fast68',x.wood5.lt(68)),('wood_5F_fast70',x.wood5.lt(70)),
                        ('wood_4F_fast52',x.wood4.lt(52)),('wood_4F_fast54',x.wood4.lt(54))]:
        x[name]=series.fillna(False);woodflags.append(x[name])
    x['wood_type']=chosen(['wood_end11_accel','wood_5F_fast68','wood_5F_fast70','wood_4F_fast52','wood_4F_fast54'],woodflags)
    for kind,timing in [('wood5',x.wood5),('wood4',x.wood4)]:
        wed=(x.wed_5F if kind=='wood5' else w4[0]).fillna(np.inf)
        thu=(x.thu_5F if kind=='wood5' else w4[1]).fillna(np.inf)
        lap=pd.Series(np.where(wed.le(thu),x.wed_Lap1,x.thu_Lap1),index=x.index).where(timing.notna())
        code=(lap*10).round().astype('Int64').astype(str)
        x[kind+'_end10']=np.select([lap.isna(),lap.lt(11),lap.between(11,11.9),lap.lt(12.5),lap.lt(13)],
                                   ['なし','<=10.9',code,'12.0-12.4','12.5-12.9'],default='13+')
    x['prior5']=pd.concat([x.sat_5F,x.sun_5F],axis=1).min(axis=1)
    x['prior4']=pd.concat([x.sat_4F.where(x.sat_5F.isna()),x.sun_4F.where(x.sun_5F.isna())],axis=1).min(axis=1).where(x.prior5.isna())
    prior_lap=pd.Series(np.where(x.sat_5F.fillna(np.inf).le(x.sun_5F.fillna(np.inf)),x.sat_Lap1,x.sun_Lap1),index=x.index).where(x.prior5.notna())
    prior_wood=x.prior5.notna()|x.prior4.notna()
    prior_hill=x.prior_clock.notna()
    x['weekend_mode']=np.select([prior_hill&prior_wood,prior_hill,prior_wood],
                                ['坂路＋ウッド','坂路のみ','ウッドのみ'],default='土日追い切りなし')
    x['trainer_weekend']=x._trainer+'/'+x.weekend_mode
    x['trainer_hill']=np.where(x.hill_type.ne('none'),x._trainer+'/'+x.hill_type,'none')
    x['trainer_wood']=np.where(x.wood_type.ne('none'),x._trainer+'/'+x.wood_type,'none')
    x['調教師']=x._trainer
    x['hill_bin']=clock(x.hill_fast,[0,50,52,54,56,58,130],['<50','50-51','52-53','54-55','56-57','58+'])
    x['prior_bin']=clock(x.prior_clock,[0,55,58,60,65,130],['<55','55-57','58-59','60-64','65+'])
    x['pre_bin']=clock(x.pre_clock,[0,65.01,68,130],['<=65','65.1-67.9','68+'])
    x['wood5_bin']=clock(x.wood5,[0,65,66,67,68,69,70,130],['<65','65','66','67','68','69','70+'])
    x['wood4_bin']=clock(x.wood4,[0,50,52,54,130],['<50','50-51','52-53','54+'])
    x['prior_wood5_bin']=clock(x.prior5,[0,66,68,70,72,74,76,120],['<66','66-67','68-69','70-71','72-73','74-75','76+'])
    x['prior_wood4_bin']=clock(x.prior4,[0,52,54,56,60,120],['<52','52-53','54-55','56-59','60+'])
    x['prior_wood_end_bin']=clock(prior_lap,[0,11.6,12,12.4,14,100],['<11.6','11.6-11.9','12.0-12.3','12.4-13.9','14+'])
    x['prior_lap_bin']=np.select([(col(x,'坂1w前 土 LAP2')>col(x,'坂1w前 土 LAP1')) & col(x,'坂1w前 土 LAP1').le(12),
                                    (col(x,'坂1w前 土 LAP2')>col(x,'坂1w前 土 LAP1'))],['A3','加速'],default='同じ/なし')
    # Replace prior lap from the fastest of the two prior hill days.
    # TARGET hill exports are newest-date first; a same-clock tie therefore
    # resolves to Sunday in the original research cache.
    satfast=col(x,'坂1w前 土 TIME1').fillna(np.inf).lt(col(x,'坂1w前 日 TIME1').fillna(np.inf))
    pr1=pd.Series(np.where(satfast,col(x,'坂1w前 土 LAP1'),col(x,'坂1w前 日 LAP1')),index=x.index)
    pr2=pd.Series(np.where(satfast,col(x,'坂1w前 土 LAP2'),col(x,'坂1w前 日 LAP2')),index=x.index)
    x['prior_lap_bin']=np.select([(pr2>pr1)&pr1.le(12),pr2>pr1,pr2<pr1],['A3','加速','減速'],default='同じ/なし')
    x['hill_end_13']=x.hill_end_13.astype(bool).astype(str)
    x['hill_accel_05']=x.hill_accel_05.astype(bool).astype(str)
    x['weekday']=x.weekday.astype(str)
    x['status']=np.where(x['場所'].isin(['函館','札幌'])|x.grade.eq('障害'),'対象外',
                         np.where(x.grade.eq('その他')|~x.weekday.isin(['0','5','6'])|~x._wood_complete,'資料不足','算出'))
    return x

def score(x:pd.DataFrame,model_path:Path)->pd.DataFrame:
    # Runtime inference uses exported logistic coefficients, so the local
    # Windows updater does not need scikit-learn to unpickle the research model.
    with Path(model_path).open(encoding='utf-8') as source:
        m=json.load(source)
    if m.get('schema')!='onehot-logistic-v1':
        raise ValueError('仕上げ指数モデルの形式が違います。JSONモデルを確認してください。')
    valid=x.status.eq('算出')
    out=x[['年月日','場所','R','馬番','馬名','調教師','weekend_mode','B1警告','status']].copy()
    out['CSV補完']=x['_source_recovered'].astype(bool) if '_source_recovered' in x else False
    out['CSV調教師判定要確認']=x['調教師判定'].astype(str).str.contains(r'^-[0-9]{5,}$',regex=True) if '調教師判定' in x else False
    # Use the same formal trainer judgment as Nexus.  The floor belongs only to
    # this separate research index; crown and probability rules remain separate.
    out['調教師判定○']=(x['_formal_trainer_ok'].astype(bool) if '_formal_trainer_ok' in x
                      else apply_trainer_rules(x)['調教師判定_正式'].astype(bool))
    # Carry only the three new rules to the app.  Other formal judgments retain
    # the existing training CSV and in-app logic.
    out['厩舎追加条件']=pd.Series(pd.NA,index=x.index,dtype='boolean')
    if '_new_trainer_condition' in x:
        selected=x['調教師'].isin(['田中博康','蛯名正義','菊沢隆徳'])
        out.loc[selected,'厩舎追加条件']=x.loc[selected,'_new_trainer_condition'].astype(bool)
    out['仕上げ点']=pd.Series(pd.NA,index=x.index,dtype='Int64')
    out['仕上げ順位値']=np.nan
    if valid.any():
        feat=x.loc[valid,m['features']].astype(str)
        def probability(kind):
            trained=m['models'][kind]
            decision=np.full(len(feat),trained['intercept'],dtype=float)
            for name in m['features']:
                decision+=feat[name].map(trained['weights'][name]).fillna(0.0).to_numpy(dtype=float)
            return 1.0/(1.0+np.exp(-decision))
        alpha=m['rank_win_weight']
        rank=(1-alpha)*probability('place')+alpha*probability('win')
        out.loc[valid,'仕上げ順位値']=rank
        point=np.searchsorted(m['point_thresholds'],rank,side='right')
        out.loc[valid,'仕上げ点']=np.where(out.loc[valid,'調教師判定○'].to_numpy(),np.maximum(point,5),point)
    return out

def attach(df:pd.DataFrame,path:Path)->pd.DataFrame:
    if not path.exists():
        out=df.copy();out['仕上げ点']=pd.NA;out['B1警告']=False;out['仕上げ状態']='未生成'
        out['厩舎追加条件']=pd.NA
        out['CSV補完']=False;out['CSV調教師判定要確認']=False
        return out
    extra=pd.read_csv(path,encoding='utf-8-sig')
    keys=['年月日','場所','R','馬番']
    for k in ['年月日','R','馬番']:
        extra[k]=num(extra[k]).astype('Int64')
    for field in ['CSV補完','CSV調教師判定要確認']:
        if field not in extra:extra[field]=False
    if '厩舎追加条件' not in extra:extra['厩舎追加条件']=pd.NA
    else:
        extra['厩舎追加条件']=extra['厩舎追加条件'].map({'True':True,'False':False,True:True,False:False}).astype('boolean')
    extra=extra[keys+['仕上げ点','B1警告','status','weekend_mode','CSV補完','CSV調教師判定要確認','厩舎追加条件']].rename(columns={'status':'仕上げ状態','weekend_mode':'前週土日調教'})
    if extra.duplicated(keys).any():raise ValueError('厩舎仕上げ指数に出走馬キーの重複があります')
    out=df.merge(extra,on=keys,how='left',validate='one_to_one')
    out['仕上げ状態']=out['仕上げ状態'].fillna('未生成')
    out['B1警告']=out['B1警告'].fillna(False).astype(bool)
    for field in ['CSV補完','CSV調教師判定要確認']:
        out[field]=out[field].fillna(False).astype(bool)
    return out
