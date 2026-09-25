# -*- coding: utf-8 -*-
"""
Runaway's Nexus - Course judgement + role classification v2.9 (2026-09-25)

Purpose
-------
Reflect the ver2.9 course-training rules directly in the racecard.
Course role is descriptive metadata only; it does not add a fixed score.

Canonical fixes included:
- A1 = LAP1 < 13.0 AND LAP2 >= 13.0
- 東京芝2400 prior-week hill acceleration requires LAP1 < 13 AND LAP1 < LAP2
- 東京芝1800 prior-week hill threshold uses AE/AH, not wood 5F
- 京都ダ1800 and 中京ダ1200 require 栗東
- 中京ダ1800 assumes corrected BE=Wednesday wood 6F and BI=Thursday wood 6F
- 新潟ダ1800 / 福島ダ1700 are removed from formal course judgement
- 東京芝1800 / 阪神芝1200 remain ordinary course judgements but are NOT crowns
"""

from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional, Tuple
import math
import pandas as pd

ALIASES = {
    "course": ["コースID","course_id","コース"],
    "aff": ["所属","所属コード","affiliation","所属区分"],
    "race_id": ["レースID","race_id","CJ"],

    "Y":["Y","坂2週前土_TIME1","坂2w前 土 TIME1"], "Z":["Z","坂2週前土_LAP1","坂2w前 土 LAP1"], "AA":["AA","坂2週前土_LAP2","坂2w前 土 LAP2"],
    "AB":["AB","坂2週前日_TIME1","坂2w前 日 TIME1"], "AC":["AC","坂2週前日_LAP1","坂2w前 日 LAP1"], "AD":["AD","坂2週前日_LAP2","坂2w前 日 LAP2"],
    "AE":["AE","坂1週前土_TIME1","坂1w前 土 TIME1"], "AF":["AF","坂1週前土_LAP1","坂1w前 土 LAP1"], "AG":["AG","坂1週前土_LAP2","坂1w前 土 LAP2"],
    "AH":["AH","坂1週前日_TIME1","坂1w前 日 TIME1"], "AI":["AI","坂1週前日_LAP1","坂1w前 日 LAP1"], "AJ":["AJ","坂1週前日_LAP2","坂1w前 日 LAP2"],
    "AK":["AK","坂水_TIME1"," 坂 水 TIME1"], "AL":["AL","坂水_LAP1"," 坂 水 LAP1"], "AM":["AM","坂水_LAP2"," 坂 水 LAP2"],
    "AP":["AP","坂木_TIME1"," 坂 木 TIME1"], "AQ":["AQ","坂木_LAP1"," 坂 木 LAP1"], "AR":["AR","坂木_LAP2"," 坂 木 LAP2"],
    "AU":["AU","坂前日_TIME1"," 坂 前日 TIME1","前日坂路時計"],

    "AV":["AV","ウ2週前土_1F","ウ2w前 土 １F"], "AW":["AW","ウ2週前日_1F","ウ2w前 日 １F"],
    "AX":["AX","ウ1週前土_1F","ウ1w前 土 １F"], "AY":["AY","ウ1週前土_5F","ウ1w前 土 5F"],
    "AZ":["AZ","ウ1週前日_1F","ウ1w前 日 １F"], "BA":["BA","ウ1週前日_5F","ウ1w前 日 5F"],
    "BB":["BB","ウ水_1F","ウ 水 1F","ウ 水1F"], "BC":["BC","ウ水_4F","ウ 水 4F"], "BD":["BD","ウ水_5F","ウ 水 5F"], "BE":["BE","ウ水_6F","ウ 水 6F"],
    "BF":["BF","ウ木_1F","ウ 木 1F","ウ 木1F"], "BG":["BG","ウ木_4F","ウ 木 4F"], "BH":["BH","ウ木_5F","ウ 木 5F"], "BI":["BI","ウ木_6F","ウ 木 6F"],
}

ROLE_MAP = {
    # 頭型 -> racecard display: 単🔥
    "東京芝1600":"単🔥",
    "東京芝2400":"単🔥",
    "東京ダ1400":"単🔥",
    "東京芝2000":"単🔥",
    "京都ダ1800":"単🔥",
    "阪神芝1600":"単🔥",
    "中京ダ1200":"単🔥",

    # 頭・軸両対応
    "東京芝1800":"単🔥・軸",

    # 軸型
    "中山芝1200":"軸",
    "中山芝2000":"軸",
    "阪神芝1200":"軸",
    "中山ダ1800":"軸",
    "東京ダ1600":"軸",
    "福島ダ1150":"軸",

    # 紐型
    "中山芝1800":"紐",
    "中京ダ1800":"紐",
    "中京芝1200":"紐・補",
    "中京芝1600":"紐・補",
    "小倉ダ1700":"紐・補",
    "阪神芝1400":"紐",

    # 慎重運用
    "福島芝1800":"単🔥・軸※",
}


REMOVED_FORMAL_COURSES = {"新潟ダ1800","福島ダ1700","中京ダ1900"}

def _get(row: Any, key: str, default=None):
    for c in ALIASES.get(key,[key]):
        if hasattr(row, "get"):
            v = row.get(c, None)
            if v is not None and not (isinstance(v,float) and math.isnan(v)):
                return v
    return default

def _num(row: Any, key: str) -> Optional[float]:
    v = _get(row,key)
    if v is None: return None
    if isinstance(v,str):
        s=v.strip().replace("秒","")
        if s in ("","-","なし","nan","None"): return None
        v=s
    try: return float(v)
    except Exception: return None

def _exists(row: Any,key:str)->bool:
    v=_get(row,key)
    if v is None: return False
    if isinstance(v,str) and v.strip() in ("","-","なし","nan","None"): return False
    return True

def _lt(row,key,x):
    v=_num(row,key); return v is not None and v < x
def _le(row,key,x):
    v=_num(row,key); return v is not None and v <= x
def _ge(row,key,x):
    v=_num(row,key); return v is not None and v >= x
def _gt(row,key,x):
    v=_num(row,key); return v is not None and v > x

def _course(row)->str:
    return str(_get(row,"course","") or "").replace(" ","").strip()

def _aff(row)->Optional[int]:
    v=_get(row,"aff")
    if v is None: return None
    s=str(v).strip()
    if s in ("2","栗東","栗"): return 2
    if s in ("1","美浦","美"): return 1
    try: return int(float(s))
    except Exception: return None

def _min(row, keys: Iterable[str])->Optional[float]:
    vals=[_num(row,k) for k in keys]
    vals=[v for v in vals if v is not None]
    return min(vals) if vals else None

def _a1(row)->bool:
    # 正本：LAP1<13 AND LAP2>=13
    return ((_lt(row,"AL",13.0) and _ge(row,"AM",13.0)) or
            (_lt(row,"AQ",13.0) and _ge(row,"AR",13.0)))

def _a2a3(row)->bool:
    al,am,aq,ar=_num(row,"AL"),_num(row,"AM"),_num(row,"AQ"),_num(row,"AR")
    return (
        (al is not None and al < 12.0) or
        (aq is not None and aq < 12.0) or
        (al is not None and am is not None and am < 13.0 and am > al) or
        (aq is not None and ar is not None and ar < 13.0 and ar > aq)
    )

def _prior_hill_exists(row): return _exists(row,"AE") or _exists(row,"AH")
def _prior_wood_exists(row): return _exists(row,"AX") or _exists(row,"AZ")
def _two_week_hill_exists(row): return _exists(row,"Y") or _exists(row,"AB")
def _current_wood_exists(row): return _exists(row,"BB") or _exists(row,"BF")

def evaluate_course_rule(row: Any, race_fastest_wood1f: Optional[float]=None) -> Tuple[bool,str]:
    c=_course(row); a=_aff(row)

    if c in REMOVED_FORMAL_COURSES:
        return False, "正式コース判定から除外"

    if c=="東京ダ1600":
        ok = (
            (a==2 and (_lt(row,"AE",60) or _lt(row,"AH",60)) and
             (_lt(row,"BB",12) or _lt(row,"BF",12) or
              (_lt(row,"AL",13) and (_num(row,"AM") is not None and _num(row,"AL") < _num(row,"AM"))) or
              (_lt(row,"AQ",13) and (_num(row,"AR") is not None and _num(row,"AQ") < _num(row,"AR")))))
            or
            (a==1 and (_le(row,"AK",53) or _le(row,"AP",53)))
        )
        return ok, "栗東：前週坂路<60＋当週W1F<12/坂路加速、または美浦：当週坂路<=53"

    if c=="東京芝1600":
        ok = ((_ge(row,"AM",13.4) and _lt(row,"AL",12.6)) or
              (_ge(row,"AR",13.4) and _lt(row,"AQ",12.6)) or
              (a==1 and (_lt(row,"AE",56) or _lt(row,"AH",56)) and (_lt(row,"BB",11.8) or _lt(row,"BF",11.8))))
        return ok, "坂路LAP1<12.6＋LAP2>=13.4、または美浦 前週坂路<56＋当週W1F<11.8"

    if c=="東京芝2400":
        # Corrected canonical form: prior-week LAP1<13 AND acceleration.
        prior_acc = ((_lt(row,"AF",13) and _num(row,"AG") is not None and _num(row,"AF") < _num(row,"AG")) or
                     (_lt(row,"AI",13) and _num(row,"AJ") is not None and _num(row,"AI") < _num(row,"AJ")))
        ok = prior_acc and (_lt(row,"BB",12) or _lt(row,"BF",12))
        return ok, "前週坂路LAP1<13かつ加速→当週ウッド1F<12"

    if c=="東京芝1800":
        # ver2.9: 2週前W必須を削除。
        ok = (a==1 and (_lt(row,"AE",58) or _lt(row,"AH",58)) and
              (_lt(row,"BB",12) or _lt(row,"BF",12)))
        return ok, "ver2.9：美浦＋前週土日坂路TIME1<58＋当週W1F<12"

    if c=="東京ダ1400":
        hill = (a==2 and _two_week_hill_exists(row) and (_prior_hill_exists(row) or _prior_wood_exists(row)) and _a2a3(row))
        wood = (a==2 and
                ((_lt(row,"BD",70) and _lt(row,"BC",54) and _le(row,"BB",12.4)) or
                 (_lt(row,"BH",70) and _lt(row,"BG",54) and _le(row,"BF",12.4))))
        return hill or wood, "栗東 坂路A2/A3型（2週前坂路＋前週坂路/W）またはW5F<70・4F<54・1F<=12.4"

    if c=="東京芝2000":
        ok = a==1 and (_le(row,"AE",58) or _le(row,"AH",58)) and _current_wood_exists(row)
        return ok, "美浦 前週坂路<=58＋当週ウッドあり"

    if c=="京都ダ1800":
        ok = a==2 and (
            _lt(row,"AL",12.4) or _lt(row,"AQ",12.4) or _lt(row,"AM",11.8) or _lt(row,"AR",11.8) or
            (_lt(row,"AM",12.8) and _num(row,"AL") is not None and _num(row,"AM") > _num(row,"AL")) or
            (_lt(row,"AR",12.8) and _num(row,"AQ") is not None and _num(row,"AR") > _num(row,"AQ"))
        )
        return ok, "栗東限定：当週坂路LAP1<12.4 / LAP2<11.8 / LAP2<12.8かつ加速"

    if c=="阪神芝1400":
        # ver2.9: 栗東＋前週土日坂路TIME1<56 のみ。
        ok = a==2 and (_lt(row,"AE",56) or _lt(row,"AH",56))
        return ok, "ver2.9：栗東＋前週土日坂路TIME1<56"

    if c=="阪神芝1600":
        ok = a==2 and (
            _lt(row,"AK",52) or _lt(row,"AP",52) or _lt(row,"AL",12) or _lt(row,"AM",12) or
            _lt(row,"AQ",12) or _lt(row,"AR",12) or _lt(row,"BB",11.6) or _lt(row,"BF",11.6)
        )
        return ok, "栗東 当週坂路<52/LAP<12 または当週W1F<11.6"

    if c=="阪神芝1200":
        branch1 = (a==2 and
                   (_lt(row,"AL",13) or _lt(row,"AQ",13) or
                    (_lt(row,"AM",13) and _num(row,"AL") is not None and _num(row,"AM") > _num(row,"AL")) or
                    (_lt(row,"AR",13) and _num(row,"AQ") is not None and _num(row,"AR") > _num(row,"AQ"))) and
                   _prior_hill_exists(row) and _lt(row,"AU",66))
        branch2 = a==2 and (_lt(row,"AE",60) or _lt(row,"AH",60)) and (_lt(row,"BD",68) or _lt(row,"BH",68))
        return branch1 or branch2, "栗東 加速/A3＋前週坂路＋前日坂路<66、または前週坂路<60＋当週W5F<68（クラウン対象外）"

    if c=="中山ダ1800":
        ok = (_lt(row,"AE",60) or _lt(row,"AH",60)) and (_lt(row,"BD",68) or _lt(row,"BH",68))
        return ok, "前週坂路<60＋当週W5F<68"

    if c=="中山芝1200":
        base = _lt(row,"AK",53) or _lt(row,"AP",53)
        al, aq = _num(row,"AL"), _num(row,"AQ")
        a3 = ((al is not None and 11.0 <= al < 12.0) or
              (aq is not None and 11.0 <= aq < 12.0))
        kur = a==2 and (_lt(row,"AE",60) or _lt(row,"AH",60)) and (_a1(row) or a3)
        mih = a==1 and (_lt(row,"AY",70) or _lt(row,"BA",70)) and _current_wood_exists(row)
        return base or kur or mih, "当週坂路<53、または栗東 前週坂路<60＋A1/A3、または美浦 前週W5F<70＋当週W"

    if c=="中山芝1800":
        ok = a==1 and (_exists(row,"AX") or _exists(row,"AZ")) and (
            (_lt(row,"BD",70) and _lt(row,"BB",12)) or (_lt(row,"BH",70) and _lt(row,"BF",12))
        )
        return ok, "美浦 前週ウッドあり＋当週W5F<70・1F<12"

    if c=="中山芝2000":
        ok = _prior_hill_exists(row) and (_lt(row,"BB",12) or _lt(row,"BF",12))
        return ok, "前週坂路あり＋当週W1F<12"

    if c=="中京ダ1200":
        # ver2.9: same-day fixed condition, Wednesday OR Thursday.
        wed = _lt(row,"AK",56) and _lt(row,"AL",13) and _gt(row,"AM",13)
        thu = _lt(row,"AP",56) and _lt(row,"AQ",13) and _gt(row,"AR",13)
        ok = a==2 and (wed or thu)
        return ok, "ver2.9：栗東＋当週坂路TIME1<56＋LAP1<13＋LAP2>13（水OR木・同日）"

    if c=="中京ダ1900":
        ok = a==2 and (_lt(row,"BC",54) or _lt(row,"BG",54))
        return ok, "ver2.9：通常コース判定から解除"

    if c=="中京ダ1800":
        ok = ((_le(row,"BE",83) and _lt(row,"BB",12)) or (_le(row,"BI",83) and _lt(row,"BF",12)))
        return ok, "当週W6F<=83＋1F<12（BE=水曜6F、BI=木曜6F）"

    if c=="中京芝1200":
        ok = a==2 and (
            _lt(row,"AM",12) or
            (_lt(row,"AK",54) and _lt(row,"AL",13) and _num(row,"AM") is not None and _num(row,"AL") < _num(row,"AM")) or
            _lt(row,"AR",12) or
            (_lt(row,"AP",54) and _lt(row,"AQ",13) and _num(row,"AR") is not None and _num(row,"AQ") < _num(row,"AR"))
        )
        return ok, "栗東 当週坂路LAP2<12、またはTIME<54＋LAP1<13かつ加速"

    if c=="中京芝1600":
        ok = a==2 and (_lt(row,"AE",60) or _lt(row,"AH",60)) and _a2a3(row)
        return ok, "栗東 前週坂路<60＋当週坂路A2/A3"

    if c=="福島ダ1150":
        # ver2.9: A3/B2条件を削除。
        ok = a==2 and _prior_hill_exists(row)
        return ok, "ver2.9：栗東＋前週土日坂路あり"

    if c=="福島芝1800":
        ok = _prior_hill_exists(row) and _a2a3(row)
        return ok, "前週坂路あり＋当週坂路A2/A3"

    if c=="小倉ダ1700":
        w1=_min(row,["BB","BF"])
        ok = w1 is not None and race_fastest_wood1f is not None and abs(w1-race_fastest_wood1f)<1e-9
        return ok, "当週ウッド1Fが同一レース内最速"

    if c.startswith("札幌ダ"):
        ok = (
            (_lt(row,"Z",13) and _num(row,"AA") is not None and _num(row,"Z") <= _num(row,"AA")) or
            (_lt(row,"AC",13) and _num(row,"AD") is not None and _num(row,"AC") <= _num(row,"AD")) or
            (_lt(row,"AF",13) and _num(row,"AG") is not None and _num(row,"AF") <= _num(row,"AG")) or
            (_lt(row,"AI",13) and _num(row,"AJ") is not None and _num(row,"AI") <= _num(row,"AJ"))
        )
        return ok, "札幌ダート：好走性能は強いがN不足のため慎重運用"

    return False, ""

def apply_course_judgement(df: pd.DataFrame) -> pd.DataFrame:
    out=df.copy()
    race_col=next((c for c in ALIASES["race_id"] if c in out.columns),None)
    course_col=next((c for c in ALIASES["course"] if c in out.columns),None)

    # Current-week wood 1F for Kokura race-level minimum.
    w1s=[]
    for _,r in out.iterrows():
        w1s.append(_min(r,["BB","BF"]))
    out["_course_w1"]=w1s

    fastest={}
    if race_col and course_col:
        cser=out[course_col].astype(str).str.replace(" ","",regex=False)
        m=cser.eq("小倉ダ1700") & out["_course_w1"].notna()
        fastest=out.loc[m].groupby(race_col)["_course_w1"].min().to_dict()

    oks=[]; reasons=[]; roles=[]
    for _,r in out.iterrows():
        rf=fastest.get(r.get(race_col)) if race_col else None
        ok,reason=evaluate_course_rule(r,rf)
        c=_course(r)
        oks.append(ok)
        reasons.append(reason if ok else "")
        if ok:
            if c.startswith("札幌ダ"):
                roles.append("単🔥※")
            else:
                roles.append(ROLE_MAP.get(c,""))
        else:
            roles.append("")

    # These are the canonical racecard columns.
    out["コース判定_bool"]=oks
    out["コース判定"]=["○" if x else "" for x in oks]
    out["コース判定理由"]=reasons
    out["コース調教役割"]=roles
    # Downstream partner/display code historically reads course_badge.
    # Keep it synchronized with the ver2.9 canonical course judgement, not the old Excel value.
    out["course_badge"]=oks
    out.drop(columns=["_course_w1"],inplace=True)
    return out
