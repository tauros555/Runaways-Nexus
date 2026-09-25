from __future__ import annotations
import pandas as pd
from modules.crown_rules_addon_v29 import apply_new_crown_rules

# 2026-09-25 formal crown policy:
# - Keep all current trainer crowns.
# - Keep only one Training○×M crown: 母母父 地-極-極.
# - Remove every Course○×M crown.
# - Course-training crowns are handled in crown_rules_addon_v29.py and limited to 3 rules.
CROWN_TRAINERS={"杉山晴紀","辻野泰之","鹿戸雄一","友道康夫","森秀行","加藤士津","竹内正洋","寺島良","吉岡辰弥","四位洋文","斎藤誠","佐藤悠太","牧浦充徳"}
TRAINER_ALIASES={"加藤士津八":"加藤士津","加藤志津":"加藤士津","斉藤誠":"斎藤誠","大久保龍":"大久保龍志"}
TRAINER_M_PATTERNS={("母母父","地極極")}
POSITIVE={"1","true","yes","有","あり","〇","○","◎","★"}

def _positive(v):
    if v is None: return False
    try:
        if pd.isna(v): return False
    except Exception: pass
    s=str(v).strip()
    return s in POSITIVE or s.lower() in POSITIVE

def normalize_trainer(name):
    s=str(name or "").strip()
    for a,c in TRAINER_ALIASES.items():
        if s.startswith(a): return c
    for c in CROWN_TRAINERS:
        if s.startswith(c): return c
    return s

def _m_values(row):
    return {"父":str(row.get("M父","") or "").strip(),
            "母父":str(row.get("M母父","") or "").strip(),
            "母母父":str(row.get("M母母父","") or "").strip()}

def evaluate_crown(row):
    reasons=[]
    trainer_ok=_positive(row.get("調教師判定",""))
    trainer=normalize_trainer(row.get("調教師",""))
    m=_m_values(row)

    # Existing trainer crowns are retained. 佐藤悠太 is crown only on A3 hit.
    if trainer_ok and trainer in CROWN_TRAINERS:
        if trainer != "佐藤悠太" or _positive(row.get("A3LAP判定","")):
            reasons.append(f"調教師判定○：{trainer}")

    # Only retained Training○×M crown.
    if trainer_ok:
        for b,p in TRAINER_M_PATTERNS:
            if m.get(b)==p:
                reasons.append(f"調教師判定○×M：{b} 地-極-極")

    reasons=list(dict.fromkeys(reasons))
    return {"crown":bool(reasons),"crown_count":len(reasons),"crown_reasons":reasons}

def add_crown_flags(df):
    out=df.copy()
    vals=out.apply(evaluate_crown,axis=1)
    legacy=[v["crown_reasons"] for v in vals]
    out=apply_new_crown_rules(out)
    merged=[]
    for old,extra in zip(legacy,out.get("追加クラウン理由",pd.Series("",index=out.index))):
        xs=list(old)
        xs += [z.strip() for z in str(extra or "").split(" / ") if z.strip()]
        merged.append(list(dict.fromkeys(xs)))
    out["crown_reasons"]=[" / ".join(x) for x in merged]
    out["crown_count"]=[len(x) for x in merged]
    out["crown_flag"]=[bool(x) for x in merged]
    out["crown_mark"]=out["crown_count"].map(lambda n:"👑" if int(n)==1 else (f"👑×{int(n)}" if int(n)>1 else ""))
    return out
