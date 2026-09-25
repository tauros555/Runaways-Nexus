from __future__ import annotations
import math
import pandas as pd

POS={"1","true","yes","有","あり","〇","○","◎","★"}
ALIASES={"大久保龍":"大久保龍志","加藤士津八":"加藤士津","加藤志津":"加藤士津","斉藤誠":"斎藤誠","中内田充正":"中内田充"}
REMOVED={"大竹正博","稲垣幸雄"}
OVERRIDE={"上村洋行","友道康夫","竹内正洋","寺島良","中内田充","高野友和","奥村豊","中竹和也","新谷功一","大久保龍志","橋口慎介"}|REMOVED

TYPE_MASTER={
"上村洋行":("軸・単🔥","MID","前週坂路＋当週W＋前日坂路","N=98 / 勝23.5% / 複56.1% / 単回130.8%"),
"友道康夫":("単🔥・軸","HIGH","水曜OR木曜 坂路LAP1<13・LAP2>=13","N=194 / 勝25.8% / 複52.1% / 単回139.7%"),
"竹内正洋":("単🔥・軸","HIGH","芝W5F<66／ダW5F<68（水OR木）","N=218 / 勝13.3% / 複30.3% / 単回138.6%"),
"寺島良":("単🔥・軸","HIGH","ダート＋前週土日坂路LAP1<13.2＋当週水木W4F<53","N=116 / 勝20.7% / 複41.4% / 単回124.4%"),
"中内田充":("単🔥・軸※","MID","当週W5F<66","N=30 / 勝36.7% / 複63.3% / 単回163.7%"),
"高野友和":("軸","LOW","芝＋坂路LAP1<12・LAP2<13・LAP2>LAP1","N=36 / 勝19.4% / 複41.7%"),
"奥村豊":("複・紐","MID","当週W5F<68＋W1F<12＋前週土日坂路あり","N=49 / 複34.7% / 非勝利2-3着28.9%"),
"中竹和也":("単🔥・軸","HIGH","前週土日坂路あり＋当週坂路TIME1<52","N=121 / 勝16.5% / 複30.6% / 単回157.4%"),
"新谷功一":("軸・単🔥","MID","当週坂路TIME1<52＋同日A2/B2/A3/B3","N=53 / 勝26.4% / 複41.5% / 単回151.1%"),
"大久保龍志":("軸","LOW","当週坂路A3またはB3","N=48 / 勝22.9% / 複47.9%"),
"橋口慎介":("補","HIGH","当週坂路TIME1<54＋同日A2/B2","N=500 / 勝11.4% / 複31.2%"),
"牧浦充徳":("単🔥","MID","正式調教師判定該当","単勝妙味型"),
"加藤士津":("単🔥・軸","HIGH","正式調教師判定該当","単勝＋軸型"),
"佐藤悠太":("補","MID","正式調教師判定該当","A3単独はクラウン条件"),
"四位洋文":("単🔥","MID","正式調教師判定該当","単勝妙味型"),
"杉山晴紀":("軸・単🔥","HIGH","正式調教師判定該当","単勝＋軸型"),
"辻野泰之":("軸・単🔥","HIGH","正式調教師判定該当","単勝＋軸型"),
"鹿戸雄一":("単🔥・軸","HIGH","正式調教師判定該当","単勝＋軸型"),
"斎藤誠":("単🔥","HIGH","正式調教師判定該当","単勝妙味型"),
"吉岡辰弥":("軸・単🔥","MID","正式調教師判定該当","単勝＋軸型"),
"森秀行":("単🔥・軸","HIGH","正式調教師判定該当","単勝＋軸型"),
}

def norm(name):
 s=str(name or '').strip()
 for a,c in ALIASES.items():
  if s.startswith(a): return c
 return s

def num(r,*keys):
 for k in keys:
  if k in r.index:
   v=r.get(k)
   if v is None: continue
   s=str(v).strip().replace('秒','')
   if s in ('','なし','nan','None','-'): continue
   try: return float(s)
   except: pass
 return None

def exists(r,*keys): return num(r,*keys) is not None

def pos(v): return str(v).strip().lower() in POS

def surface(r):
 s=str(r.get('芝・ダ','')).strip(); return '芝' if s.startswith('芝') else ('ダ' if s.startswith('ダ') else s)
def aff(r): return str(r.get('所属','')).strip()

def day(r,d):
 if d=='wed': return (num(r,' 坂 水 TIME1'),num(r,' 坂 水 LAP1'),num(r,' 坂 水 LAP2'))
 return (num(r,' 坂 木 TIME1'),num(r,' 坂 木 LAP1'),num(r,' 坂 木 LAP2'))
def wood(r,d):
 if d=='wed': return (num(r,'ウ 水 1F','ウ 水1F'),num(r,'ウ 水 4F'),num(r,'ウ 水 5F'))
 return (num(r,'ウ 木 1F','ウ 木1F'),num(r,'ウ 木 4F'),num(r,'ウ 木 5F'))
def prior_hill(r): return exists(r,'坂1w前 土 TIME1') or exists(r,'坂1w前 日 TIME1')
def prior_lap1_lt(r,x):
 a=num(r,'坂1w前 土 LAP1'); b=num(r,'坂1w前 日 LAP1'); return (a is not None and a<x) or (b is not None and b<x)
def current_wood(r): return any(v is not None for d in ('wed','thu') for v in wood(r,d))
def day_before(r): return exists(r,' 坂 前日 TIME1','前日坂路時計')

def a2(l1,l2): return l1 is not None and l2 is not None and 12.0<=l2<13.0 and l2<l1
def b2(l1,l2): return l1 is not None and l2 is not None and 12.0<=l2<13.0 and l2>l1
def a3(l1,l2): return l1 is not None and 11.0<=l1<12.0
def b3(l1,l2): return l1 is not None and l2 is not None and 11.0<=l2<12.0 and l2>l1
def cls(l1,l2): return a2(l1,l2) or b2(l1,l2) or a3(l1,l2) or b3(l1,l2)

def formal_trainer_rule(r):
 t=norm(r.get('調教師',''))
 if t in REMOVED: return False
 if t not in OVERRIDE: return pos(r.get('調教師判定',''))
 wd=[day(r,'wed'),day(r,'thu')]; ww=[wood(r,'wed'),wood(r,'thu')]
 if t=='上村洋行': return surface(r)=='芝' and prior_hill(r) and current_wood(r) and day_before(r)
 if t=='友道康夫': return surface(r)=='芝' and aff(r) in ('栗','栗東','2') and any(l1 is not None and l2 is not None and l1<13 and l2>=13 for _,l1,l2 in wd)
 if t=='竹内正洋':
  lim=66 if surface(r)=='芝' else (68 if surface(r)=='ダ' else None)
  return lim is not None and any(f5 is not None and f5<lim for _,_,f5 in ww)
 if t=='寺島良': return surface(r)=='ダ' and prior_lap1_lt(r,13.2) and any(f4 is not None and f4<53 for _,f4,_ in ww)
 if t=='中内田充': return any(f5 is not None and f5<66 for _,_,f5 in ww)
 if t=='高野友和': return surface(r)=='芝' and any(l1 is not None and l2 is not None and l1<12 and l2<13 and l2>l1 for _,l1,l2 in wd)
 if t=='奥村豊': return prior_hill(r) and any(f1 is not None and f5 is not None and f5<68 and f1<12 for f1,_,f5 in ww)
 if t=='中竹和也': return prior_hill(r) and any(tm is not None and tm<52 for tm,_,_ in wd)
 if t=='新谷功一': return any(tm is not None and tm<52 and cls(l1,l2) for tm,l1,l2 in wd)
 if t=='大久保龍志': return any(a3(l1,l2) or b3(l1,l2) for _,l1,l2 in wd)
 if t=='橋口慎介': return any(tm is not None and tm<54 and (a2(l1,l2) or b2(l1,l2)) for tm,l1,l2 in wd)
 return False

def apply_trainer_rules(df):
 out=df.copy(); flags=[]; labels=[]; reasons=[]; stats=[]; conf=[]
 for _,r in out.iterrows():
  ok=formal_trainer_rule(r); t=norm(r.get('調教師','')); meta=TYPE_MASTER.get(t)
  flags.append(ok)
  if ok and meta:
   labels.append(meta[0]); conf.append(meta[1]); reasons.append(meta[2]); stats.append(meta[3])
  elif ok:
   labels.append('○'); conf.append(''); reasons.append('正式調教師判定該当'); stats.append('')
  else:
   labels.append(''); conf.append(''); reasons.append(''); stats.append('')
 out['調教師判定_正式']=flags
 out['厩舎タイプ']=labels
 out['厩舎信頼度']=conf
 out['厩舎理由']=reasons
 out['厩舎統計']=stats
 # Make downstream existing logic consume v2.6 without double-scoring type.
 out['調教師判定']=flags
 return out
