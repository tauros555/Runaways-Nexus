from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
PED_DIR = BASE / "data" / "pedigree"

TURF_MASTER = PED_DIR / "turf_master.csv"
DIRT_MASTER = PED_DIR / "dirt_master.csv"
COURSE_MASTER = PED_DIR / "course_master.csv"

GRADE_TO_FEATURE = {"◎": 1.0, "○": 0.5, "〇": 0.5, "△": 0.0, "×": -1.0, "-": 0.0}


def _read_any(path: Path) -> pd.DataFrame:
    last = None
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except Exception as e:
            last = e
    raise RuntimeError(f"CSV読込失敗: {path.name}: {last}")


def load_masters() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    turf = _read_any(TURF_MASTER)
    dirt = _read_any(DIRT_MASTER)
    course = _read_any(COURSE_MASTER)
    for df in (turf, dirt, course):
        df.columns = [str(c).strip() for c in df.columns]
    turf = turf.rename(columns={"レース番号": "R"})
    dirt = dirt.rename(columns={"芝ダ": "芝・ダ"})
    # Normalize surface labels.
    for df in (turf, dirt):
        if "芝ダ" in df.columns and "芝・ダ" not in df.columns:
            df["芝・ダ"] = df["芝ダ"]
        if "父馬名" in df.columns:
            df["父馬名"] = df["父馬名"].astype(str).str.strip()
    return turf, dirt, course


def _rate_summary(df: pd.DataFrame) -> dict[str, float]:
    finish = pd.to_numeric(df.get("確定着順"), errors="coerce").dropna()
    n = len(finish)
    if n == 0:
        return {"sample": 0, "win": 0, "place": 0, "win_rate": 0.0, "place_rate": 0.0}
    return {
        "sample": int(n),
        "win": int((finish == 1).sum()),
        "place": int((finish <= 3).sum()),
        "win_rate": float((finish == 1).mean() * 100),
        "place_rate": float((finish <= 3).mean() * 100),
    }


def _two_sided_normal_p(x: int, n: int, p0: float) -> float:
    if n <= 0 or p0 <= 0 or p0 >= 1:
        return 1.0
    sd = math.sqrt(n * p0 * (1 - p0))
    if sd == 0:
        return 1.0
    z = (x - n * p0) / sd
    return float(math.erfc(abs(z) / math.sqrt(2)))


def _confidence(sample: int, win_diff: float, place_diff: float, p_value: float) -> float:
    sample_score = min(max(sample, 0) / 30.0, 1.0)
    effect_score = min((abs(win_diff) / 5.0 + abs(place_diff) / 10.0) / 2.0, 1.0)
    if p_value <= 0.05:
        sig_score = 1.0
    elif p_value <= 0.10:
        sig_score = 0.7
    elif p_value <= 0.20:
        sig_score = 0.4
    else:
        sig_score = 0.15
    return round(min(max(sample_score * 0.50 + effect_score * 0.35 + sig_score * 0.15, 0.0), 1.0), 4)


def _effect_stats(target: pd.DataFrame, base: pd.DataFrame) -> dict[str, Any]:
    t = _rate_summary(target)
    b = _rate_summary(base)
    if t["sample"] == 0 or b["sample"] == 0:
        return {**t, "base_sample": int(b["sample"]), "stat_score": 0.0, "confidence_score": 0.0,
                "win_rate_diff": 0.0, "place_rate_diff": 0.0, "rr": 1.0, "p_value": 1.0}
    win_diff = t["win_rate"] - b["win_rate"]
    place_diff = t["place_rate"] - b["place_rate"]
    rr = t["win_rate"] / b["win_rate"] if b["win_rate"] > 0 else 1.0
    p = _two_sided_normal_p(t["win"], t["sample"], b["win_rate"] / 100.0)
    conf = _confidence(t["sample"], win_diff, place_diff, p)
    raw = win_diff * 0.55 + place_diff * 0.30 + math.log(max(rr, 0.05)) * 2.0 * 0.15
    return {
        **t,
        "base_sample": int(b["sample"]),
        "base_win_rate": round(float(b["win_rate"]), 3),
        "base_place_rate": round(float(b["place_rate"]), 3),
        "win_rate_diff": round(float(win_diff), 3),
        "place_rate_diff": round(float(place_diff), 3),
        "rr": round(float(rr), 4),
        "p_value": round(float(p), 5),
        "confidence_score": conf,
        "stat_score": round(float(raw * conf), 4),
    }


def _grade(stats: dict[str, Any]) -> str:
    if int(stats.get("sample", 0) or 0) < 5:
        return "-"
    score = float(stats.get("stat_score", 0) or 0)
    conf = float(stats.get("confidence_score", 0) or 0)
    win_diff = float(stats.get("win_rate_diff", 0) or 0)
    place_diff = float(stats.get("place_rate_diff", 0) or 0)
    if score >= 2.5 and conf >= 0.55:
        return "◎"
    if score >= 0.8 and (win_diff > 0 or place_diff > 0):
        return "○"
    if score <= -1.2 and conf >= 0.45:
        return "×"
    return "△"


def _eval_condition(sire_df: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    stats = _effect_stats(sire_df[mask], sire_df)
    g = _grade(stats)
    return {"grade": g, "feature": GRADE_TO_FEATURE[g], "stats": stats}


def _course_info(course_df: pd.DataFrame, course_id: str, place: str, surface: str, distance: float) -> dict[str, Any]:
    if course_id and "コースID" in course_df.columns:
        hit = course_df[course_df["コースID"].astype(str).str.strip() == str(course_id).strip()]
        if len(hit):
            return hit.iloc[0].to_dict()
    surf = "芝" if str(surface).strip() == "芝" else "ダ"
    z = course_df[
        (course_df["場所"].astype(str).str.strip() == str(place).strip())
        & (course_df["芝・ダ"].astype(str).str.strip().isin([surf, "ダート" if surf == "ダ" else surf]))
        & (pd.to_numeric(course_df["距離"], errors="coerce") == float(distance))
    ]
    return z.iloc[0].to_dict() if len(z) else {}


def evaluate_pedigree_core(current: pd.DataFrame, turf: pd.DataFrame, dirt: pd.DataFrame, course: pd.DataFrame) -> pd.DataFrame:
    """Evaluate the three validated Pedigree Core elements for each current runner.

    Uses the existing SireAnalyzer philosophy: condition performance is compared
    with the sire's own baseline, not absolute sire win rate.
    """
    rows = []
    for _, r in current.iterrows():
        surface = "芝" if str(r.get("芝・ダ", "")).strip() == "芝" else "ダ"
        master = turf if surface == "芝" else dirt
        sire = str(r.get("父", r.get("父馬名", ""))).strip()
        sire_df = master[master["父馬名"].astype(str).str.strip() == sire].copy()
        info = _course_info(course, str(r.get("コースID", "")), str(r.get("場所", "")), surface, float(r.get("距離", 0) or 0))
        if sire_df.empty or not info:
            rows.append({
                "馬番": r.get("馬番"), "ped_distance_grade": "-", "ped_turn_grade": "-", "ped_slope_grade": "-",
                "ped_distance": 0.0, "ped_turn": 0.0, "ped_slope": 0.0,
                "pedigree_core_score": 0.0, "pedigree_core_grade": "-",
            })
            continue
        dtype = str(info.get("距離区分", "")).strip()
        turn = str(info.get("右左", "")).strip()
        slope = str(info.get("坂", "")).strip()
        # Historical masters do not always carry these course attributes. Map by course ID.
        if "距離区分" not in sire_df.columns or "右左" not in sire_df.columns or "坂" not in sire_df.columns:
            enrich = course[[c for c in ["コースID", "距離区分", "右左", "坂"] if c in course.columns]].drop_duplicates("コースID")
            sire_df = sire_df.merge(enrich, on="コースID", how="left", suffixes=("", "_course"))
        dres = _eval_condition(sire_df, sire_df.get("距離区分", pd.Series("", index=sire_df.index)).astype(str).str.strip() == dtype)
        tres = _eval_condition(sire_df, sire_df.get("右左", pd.Series("", index=sire_df.index)).astype(str).str.strip() == turn)
        sres = _eval_condition(sire_df, sire_df.get("坂", pd.Series("", index=sire_df.index)).astype(str).str.strip() == slope)
        core_score = 0.258 * dres["feature"] + 0.327 * tres["feature"] + 0.137 * sres["feature"]
        if core_score >= 0.55:
            core_grade = "◎"
        elif core_score >= 0.30:
            core_grade = "○"
        elif core_score > 0:
            core_grade = "△"
        elif core_score < -0.10:
            core_grade = "×"
        else:
            core_grade = "-"
        rows.append({
            "馬番": r.get("馬番"),
            "ped_distance_grade": dres["grade"], "ped_turn_grade": tres["grade"], "ped_slope_grade": sres["grade"],
            "ped_distance": dres["feature"], "ped_turn": tres["feature"], "ped_slope": sres["feature"],
            "pedigree_core_score": round(core_score, 4), "pedigree_core_grade": core_grade,
            "ped_distance_n": dres["stats"].get("sample", 0), "ped_turn_n": tres["stats"].get("sample", 0), "ped_slope_n": sres["stats"].get("sample", 0),
        })
    return pd.DataFrame(rows)
