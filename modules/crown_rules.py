from __future__ import annotations

import pandas as pd

CROWN_TRAINERS = {
    "牧浦充徳","加藤士津","佐藤悠太","四位洋文","辻野泰之",
    "鹿戸雄一","斎藤誠","吉岡辰弥","森秀行",
}

TRAINER_ALIASES = {
    "加藤士津八":"加藤士津",
    "加藤志津":"加藤士津",
    "斉藤誠":"斎藤誠",
}

TRAINER_M_PATTERNS = {
    ("母母父","極極極"),
    ("父","地地地"),
    ("母父","極極極"),
    ("母父","極極地"),
    ("父","地バ極"),
    ("母母父","地極極"),
}

COURSE_M_PATTERNS = {
    ("母父","極極極"),
    ("母父","極地地"),
    ("母父","地地地"),
    ("父","地バ極"),
}

POSITIVE={"1","true","yes","有","あり","〇","○","◎","★"}

def _positive(v) -> bool:
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except Exception:
        pass
    s=str(v).strip()
    return s in POSITIVE or s.lower() in POSITIVE

def normalize_trainer(name: object) -> str:
    if name is None:
        return ""
    s=str(name).strip()
    if s.lower() in {"","nan","none","<na>"}:
        return ""
    for alias,canonical in TRAINER_ALIASES.items():
        if s.startswith(alias):
            return canonical
    for canonical in CROWN_TRAINERS:
        if s.startswith(canonical):
            return canonical
    return s

def _m_values(row: pd.Series) -> dict[str,str]:
    return {
        "父":str(row.get("M父","") or "").strip(),
        "母父":str(row.get("M母父","") or "").strip(),
        "母母父":str(row.get("M母母父","") or "").strip(),
    }

def evaluate_crown(row: pd.Series) -> dict:
    reasons=[]
    trainer_ok=_positive(row.get("調教師判定",""))
    trainer=normalize_trainer(row.get("調教師",""))
    course_ok=_positive(row.get("コース判定","")) or bool(row.get("course_badge",False))
    mvals=_m_values(row)

    if trainer_ok and trainer in CROWN_TRAINERS:
        reasons.append(f"調教師判定○：{trainer}")

    if trainer_ok:
        for block,pattern in TRAINER_M_PATTERNS:
            if mvals.get(block)==pattern:
                reasons.append(f"調教師判定○×M：{block} {pattern}")

    if course_ok:
        for block,pattern in COURSE_M_PATTERNS:
            if mvals.get(block)==pattern:
                reasons.append(f"コース判定○×M：{block} {pattern}")

    reasons=list(dict.fromkeys(reasons))
    return {
        "crown":bool(reasons),
        "crown_count":len(reasons),
        "crown_reasons":reasons,
    }

def add_crown_flags(df: pd.DataFrame) -> pd.DataFrame:
    out=df.copy()
    vals=out.apply(evaluate_crown,axis=1)
    out["crown_flag"]=[v["crown"] for v in vals]
    out["crown_count"]=[v["crown_count"] for v in vals]
    out["crown_reasons"]=[" / ".join(v["crown_reasons"]) for v in vals]
    out["crown_mark"]=out["crown_count"].map(
        lambda n:"👑" if int(n)==1 else (f"👑×{int(n)}" if int(n)>1 else "")
    )
    return out
