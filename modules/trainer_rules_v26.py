from __future__ import annotations
import pandas as pd

POS={"1","true","yes","有","あり","〇","○","◎","★"}
ALIASES={"大久保龍":"大久保龍志","加藤士津八":"加藤士津","加藤志津":"加藤士津","斉藤誠":"斎藤誠","中内田充正":"中内田充"}
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
"田中博康":("軸","HIGH","ダート＋前週土日坂路<56","ダ n=83 / 勝33.7% / 複55.4% / 単回105.9% / 勝・複とも5/5年優位"),
"蛯名正義":("単🔥","MID","芝＋前週土日坂路<56","芝 n=57 / 勝21.1% / 複35.1% / 単回147.0% / 比較可能4/4年優位"),
"菊沢隆徳":("単🔥","MID","芝＋当週水木坂路の加速ラップ","芝 n=167 / 勝13.8% / 複29.9% / 単回132.0% / 勝率5/5年優位"),
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

def pos(v):
 return str(v).strip().lower() in POS

def formal_trainer_rule(r):
 """Excel由来の調教師判定を正本とし、時計から再判定しない。"""
 if '調教師判定' not in r.index:
  raise ValueError('Excel由来の「調教師判定」列が必要です。')
 return pos(r['調教師判定'])

def apply_trainer_rules(df):
 if '調教師判定' not in df.columns:
  raise ValueError('Excel由来の「調教師判定」列が必要です。')
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
 # Excel判定を真偽値へ正規化するだけで、採否は変えない。
 out['調教師判定']=flags
 return out
