# -*- coding: utf-8 -*-
"""
Runaway's Nexus - Formal Crown add-on v2.9 (2026-09-25)

Important:
- 2026-09-25 crown policy: this add-on contains ONLY the three retained course crowns.
- Trainer crowns and the single retained Training○×M crown are handled in crown_rules.py.
- All Course○×M crowns and all other former course crowns are removed.
- No fixed probability/Core score bonus is applied.
- A1 canonical definition for the retained Nakayama turf 1200 crown:
    LAP1 < 13.0 and LAP2 >= 13.0 (Wednesday OR Thursday)
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import math
import pandas as pd

FORMAL_CROWN_MASTER = Path(__file__).resolve().parent.parent / "data" / "crown_master_v29_20260925.csv"

# Column aliases. The first matching name is used.
ALIASES = {
    "course": ["コースID", "course_id", "コース"],
    "aff": ["所属", "所属コード", "affiliation", "所属区分"],
    "race_id": ["レースID", "race_id", "CJ"],

    "Y":  ["Y","坂2週前土_TIME1","坂2w前土_TIME1","坂路2週前土_TIME1"],
    "AB": ["AB","坂2週前日_TIME1","坂2w前日_TIME1","坂路2週前日_TIME1"],
    "AE": ["AE","坂1週前土_TIME1","坂1w前土_TIME1","坂路1週前土_TIME1","坂1w前 土 TIME1"],
    "AH": ["AH","坂1週前日_TIME1","坂1w前日_TIME1","坂路1週前日_TIME1","坂1w前 日 TIME1"],
    "AK": ["AK","坂水_TIME1","坂路水_TIME1"],
    "AL": ["AL","坂水_LAP1","坂路水_LAP1"," 坂 水 LAP1"],
    "AM": ["AM","坂水_LAP2","坂路水_LAP2"," 坂 水 LAP2"],
    "AP": ["AP","坂木_TIME1","坂路木_TIME1"],
    "AQ": ["AQ","坂木_LAP1","坂路木_LAP1"," 坂 木 LAP1"],
    "AR": ["AR","坂木_LAP2","坂路木_LAP2"," 坂 木 LAP2"],

    "AX": ["AX","ウ1週前土_1F","ウッド1週前土_1F","ウ1w前 土 １F"],
    "AY": ["AY","ウ1週前土_5F","ウッド1週前土_5F","ウ1w前 土 5F"],
    "AZ": ["AZ","ウ1週前日_1F","ウッド1週前日_1F","ウ1w前 日 １F"],
    "BA": ["BA","ウ1週前日_5F","ウッド1週前日_5F","ウ1w前 日 5F"],
    "BB": ["BB","ウ水_1F","ウッド水_1F","ウ 水 1F","ウ 水1F"],
    "BC": ["BC","ウ水_4F","ウッド水_4F","ウ 水 4F"],
    "BD": ["BD","ウ水_5F","ウッド水_5F","ウ 水 5F"],
    "BF": ["BF","ウ木_1F","ウッド木_1F","ウ 木 1F","ウ 木1F"],
    "BG": ["BG","ウ木_4F","ウッド木_4F","ウ 木 4F"],
    "BH": ["BH","ウ木_5F","ウッド木_5F","ウ 木 5F"],

    "course_ok": ["コース判定", "course_judgement", "course_ok", "CC"],

    "sire": ["父", "父馬", "種牡馬", "sire"],
    "m_f1": ["父_父M", "M_父1"],
    "m_f2": ["父_母父M", "M_父2"],
    "m_f3": ["父_母母父M", "M_父3"],
    "m_b1": ["母父_父M", "M_母父1"],
    "m_b2": ["母父_母父M", "M_母父2"],
    "m_b3": ["母父_母母父M", "M_母父3"],
}

@dataclass
class CrownHit:
    rule_id: str
    display: str
    category: str
    role: str
    user_override: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def _get(row: Any, key: str, default=None):
    aliases = ALIASES.get(key, [key])
    if hasattr(row, "get"):
        for c in aliases:
            try:
                v = row.get(c, None)
            except Exception:
                v = None
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                return v
    return default

def _num(row: Any, key: str) -> Optional[float]:
    v = _get(row, key)
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip().replace("秒","")
        if s in ("", "-", "なし", "nan", "None"):
            return None
        v = s
    try:
        return float(v)
    except Exception:
        return None

def _exists(row: Any, key: str) -> bool:
    v = _get(row, key)
    if v is None:
        return False
    if isinstance(v, str) and v.strip() in ("", "-", "なし", "nan", "None"):
        return False
    return True

def _lt(row, key, x):
    v = _num(row,key)
    return v is not None and v < x

def _le(row, key, x):
    v = _num(row,key)
    return v is not None and v <= x

def _ge(row, key, x):
    v = _num(row,key)
    return v is not None and v >= x

def _course(row) -> str:
    return str(_get(row,"course","") or "").replace(" ", "").strip()

def _aff(row) -> Optional[int]:
    v = _get(row,"aff")
    if v is None:
        return None
    s = str(v).strip()
    if s in ("2","栗東","栗"):
        return 2
    if s in ("1","美浦","美"):
        return 1
    try:
        return int(float(s))
    except Exception:
        return None

def _course_ok(row) -> bool:
    v = _get(row,"course_ok")
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("true","1","○","〇","yes","ok","該当")

def _a1(row) -> bool:
    # Canonical A1: LAP1 < 13.0 AND LAP2 >= 13.0
    return ((_lt(row,"AL",13.0) and _ge(row,"AM",13.0)) or
            (_lt(row,"AQ",13.0) and _ge(row,"AR",13.0)))

def _a2a3(row) -> bool:
    # 2026-09-23 course validation reproduction formula.
    al, am, aq, ar = _num(row,"AL"), _num(row,"AM"), _num(row,"AQ"), _num(row,"AR")
    return (
        (al is not None and al < 12.0) or
        (aq is not None and aq < 12.0) or
        (am is not None and al is not None and am < 13.0 and am > al) or
        (ar is not None and aq is not None and ar < 13.0 and ar > aq)
    )

def _a1_or_a3(row) -> bool:
    # Canonical A3: LAP1 in [11.0, 12.0), Wednesday OR Thursday.
    al, aq = _num(row,"AL"), _num(row,"AQ")
    a3 = ((al is not None and 11.0 <= al < 12.0) or
          (aq is not None and 11.0 <= aq < 12.0))
    return _a1(row) or a3

def _prior_hill_exists(row) -> bool:
    return _exists(row,"AE") or _exists(row,"AH")

def _prior_wood_exists(row) -> bool:
    return _exists(row,"AX") or _exists(row,"AZ")

def _two_week_hill_exists(row) -> bool:
    return _exists(row,"Y") or _exists(row,"AB")

def _current_wood_exists(row) -> bool:
    return _exists(row,"BB") or _exists(row,"BF")

def _min_num(row, keys: Iterable[str]) -> Optional[float]:
    vals = [_num(row,k) for k in keys]
    vals = [v for v in vals if v is not None]
    return min(vals) if vals else None

def _m(row, key: str) -> str:
    v = _get(row,key,"")
    return str(v).strip()

def _new_course_training_hits(row, kokura_race_fastest_1f: Optional[float]=None) -> List[CrownHit]:
    """2026-09-25 formal course crowns: exactly three rules."""
    c = _course(row)
    a = _aff(row)
    hits: List[CrownHit] = []

    if c == "中山芝1200":
        prior_hill = _min_num(row,["AE","AH"])
        if a == 2 and prior_hill is not None and prior_hill < 60.0 and _a1_or_a3(row):
            hits.append(CrownHit("CRS_001","👑 中山芝1200 栗東A1/A3型","COURSE_TRAINING","軸"))
        prior_w5 = _min_num(row,["AY","BA"])
        if a == 1 and prior_w5 is not None and prior_w5 < 70.0 and _current_wood_exists(row):
            hits.append(CrownHit("CRS_002","👑 中山芝1200 美浦ウッド型","COURSE_TRAINING","軸"))

    elif c == "東京ダ1400":
        # Retain only the 栗東W branch. The former hill branch is no longer a crown.
        w5 = _min_num(row,["BD","BH"])
        w4 = _min_num(row,["BC","BG"])
        w1 = _min_num(row,["BB","BF"])
        if a == 2 and w5 is not None and w5 < 70.0 and w4 is not None and w4 < 54.0 and w1 is not None and w1 <= 12.4:
            hits.append(CrownHit("CRS_005","👑 東京ダ1400 栗東ウッド型","COURSE_TRAINING","単🔥"))

    return hits


def apply_new_crown_rules(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds:
      - 追加クラウン判定
      - 追加クラウン理由
      - 追加クラウン役割
      - 追加クラウン件数
      - 追加クラウンUSER_OVERRIDE

    Existing crown columns are not overwritten.
    """
    out = df.copy()

    displays, roles, counts, overrides = [], [], [], []
    for _, row in out.iterrows():
        hits = _new_course_training_hits(row)
        displays.append(" / ".join(h.display for h in hits) if hits else "")
        roles.append(" / ".join(dict.fromkeys(h.role for h in hits)) if hits else "")
        counts.append(len(hits))
        overrides.append(any(h.user_override for h in hits))

    out["追加クラウン判定"] = ["👑" if n else "" for n in counts]
    out["追加クラウン理由"] = displays
    out["追加クラウン役割"] = roles
    out["追加クラウン件数"] = counts
    out["追加クラウンUSER_OVERRIDE"] = overrides
    return out

def merge_display(existing_display: Any, addon_display: Any) -> str:
    """UI helper: keep existing crown display and append only new formal crowns."""
    a = "" if existing_display is None else str(existing_display).strip()
    b = "" if addon_display is None else str(addon_display).strip()
    if not a:
        return b
    if not b:
        return a
    return f"{a} / {b}"
