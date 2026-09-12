from __future__ import annotations

import math
import numpy as np
import pandas as pd

# Partner Ver.3 formal ranking weights.
# Fixed after 2024->2025->2026 chronological validation.
# These are ranking weights, NOT calibrated conditional place probabilities.
PARTNER_V3_WEIGHTS = {
    "development": 0.25,
    "pedigree": 0.10,
    "surface": 0.05,
    "training": 0.00,
    "ability": 0.60,
}

_POS = {"◎", "○", "〇", "◯", "1", "true", "有", "あり"}
_FRONT = {"逃げ", "先行", "好位", "前"}
_MID = {"中団", "中"}
_BACK = {"差し", "追込", "追い込み", "後方", "後"}


def _num(v, default=0.0) -> float:
    try:
        z = float(v)
        return default if math.isnan(z) else z
    except Exception:
        return default


def _positive(v) -> int:
    return int(str(v).strip().lower() in _POS)


def _style_group(v: object) -> str:
    s = str(v or "").strip()
    if any(k in s for k in _FRONT):
        return "front"
    if any(k in s for k in _MID):
        return "mid"
    if any(k in s for k in _BACK):
        return "back"
    return "unknown"


def _grade_positive(v: object) -> float:
    s = str(v or "").strip()
    if s == "◎": return 1.0
    if s in {"○", "〇", "◯"}: return 0.7
    if s == "△": return 0.25
    if s == "×": return 0.0
    return 0.0


def _percentile(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0.0)
    if len(s) <= 1:
        return pd.Series(0.5, index=s.index)
    return s.rank(method="average", pct=True)


def anchor_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """Return training-first anchor candidates.

    Priority philosophy:
      - trainer rule or high-win A3
      - no effective Jirai
      - rank by training strength, then Final Nexus / place ability
    """
    x = df.copy()
    trainer = x.get("trainer_rule", x.get("調教師判定", pd.Series(0, index=x.index))).map(_positive) if "trainer_rule" not in x.columns else pd.to_numeric(x["trainer_rule"], errors="coerce").fillna(0).astype(int)
    high = x.get("a3_high", x.get("A3高勝率Lap", pd.Series(0, index=x.index))).map(_positive) if "a3_high" not in x.columns else pd.to_numeric(x["a3_high"], errors="coerce").fillna(0).astype(int)
    jirai = pd.to_numeric(x.get("jirai", x.get("jirai_badge", 0)), errors="coerce").fillna(0).astype(int)
    x["partner_anchor_eligible"] = ((trainer.eq(1) | high.eq(1)) & jirai.eq(0))
    x["partner_anchor_priority"] = (
        trainer * 3
        + high * 2
        + pd.to_numeric(x.get("training_stars", 0), errors="coerce").fillna(0)
        + pd.to_numeric(x.get("final_nexus_prob", x.get("nexus_base_prob", 0)), errors="coerce").fillna(0)
    )
    return x.sort_values(["partner_anchor_eligible", "partner_anchor_priority"], ascending=[False, False])


def _development_component(anchor: pd.Series, cand: pd.Series) -> tuple[float, list[str]]:
    """Explainable Partner Ver.3 development compatibility.

    2024-2026 reason validation consistently supported front/mid coexistence and
    penalized combinations involving a back-position partner. 2026 formal RD
    also showed a strong negative for extreme (>=400m) distance changes among
    non-favourites.
    """
    reasons: list[str] = []
    ag = _style_group(anchor.get("今回想定脚質", anchor.get("脚質", "")))
    cg = _style_group(cand.get("今回想定脚質", cand.get("脚質", "")))

    if ag == "front" and cg == "front":
        score = 0.90
        reasons.append("本命と前方帯で展開両立")
    elif (ag, cg) in {("front", "mid"), ("mid", "front")} :
        score = 0.85
        reasons.append("本命と前〜中団で展開両立")
    elif ag == "mid" and cg == "mid":
        score = 0.70
        reasons.append("本命と中団帯で展開両立")
    elif "back" in {ag, cg}:
        score = 0.20
        reasons.append("後方依存で本命好走シナリオとの連動弱め")
    else:
        score = 0.45

    # Candidate's own formal development grade is supportive, not the core reason.
    ce = str(cand.get("展開評価", ""))
    if ce in {"◎", "○", "〇", "◯", "A", "B"}:
        score += 0.08
        reasons.append("相手自身の展開評価も良好")

    # 2026 formal holdout: extreme +/-400m changes were strongly negative
    # among non-favourites. Keep as a bounded penalty until longer validation.
    bucket = str(cand.get("距離変化区分", ""))
    if bucket in {"短縮400m+", "延長400m+"}:
        score -= 0.25
        reasons.append("極端な距離変化は暫定減点")

    return float(np.clip(score, 0.0, 1.0)), reasons

def _pedigree_component(anchor: pd.Series, cand: pd.Series) -> tuple[float, list[str]]:
    reasons: list[str] = []
    pairs = [
        ("ped_distance_grade", "距離適性共有"),
        ("ped_turn_grade", "左右適性共有"),
        ("ped_slope_grade", "坂適性共有"),
    ]
    shared = []
    own = []
    for col, label in pairs:
        a = _grade_positive(anchor.get(col, "-"))
        c = _grade_positive(cand.get(col, "-"))
        shared.append(min(a, c))
        own.append(c)
        if min(a, c) >= 0.7:
            reasons.append(label)
    # Shared condition fit is primary; candidate's own fit prevents zeroing when anchor is neutral.
    score = 0.75 * (sum(shared) / len(shared)) + 0.25 * (sum(own) / len(own))
    return float(np.clip(score, 0.0, 1.0)), reasons


def _surface_component(anchor: pd.Series, cand: pd.Series) -> tuple[float, list[str]]:
    reasons: list[str] = []
    afb, cfb = _num(anchor.get("front_back_fit", 0)), _num(cand.get("front_back_fit", 0))
    aio, cio = _num(anchor.get("inside_outside_fit", 0)), _num(cand.get("inside_outside_fit", 0))
    # Pair agreement: 1 when same sign/value, lower when opposed.
    fb_agree = max(0.0, 1.0 - min(abs(afb - cfb), 2.0) / 2.0)
    io_agree = max(0.0, 1.0 - min(abs(aio - cio), 2.0) / 2.0)
    own_beta = _num(cand.get("sire_surface_adjustment", 0)) + _num(cand.get("day_bias_adjustment", 0))
    own = 0.5 + 0.5 * math.tanh(own_beta * 2.5)
    score = 0.45 * fb_agree + 0.30 * io_agree + 0.25 * own
    if fb_agree >= 0.85 and (abs(afb) > 0.1 or abs(cfb) > 0.1):
        reasons.append("当日の前後Bias恩恵を共有")
    if io_agree >= 0.85 and (abs(aio) > 0.1 or abs(cio) > 0.1):
        reasons.append("当日の内外Bias恩恵を共有")
    if own_beta > 0.05:
        reasons.append("相手自身の馬場適性がプラス")
    return float(np.clip(score, 0.0, 1.0)), reasons


def _training_component(cand: pd.Series) -> tuple[float, list[str], bool]:
    reasons: list[str] = []
    jirai = int(_num(cand.get("jirai", cand.get("jirai_badge", 0)), 0))
    if jirai:
        return 0.0, ["地雷ラップ"], True
    stars = int(_num(cand.get("training_stars", 0), 0))
    trainer = int(_num(cand.get("trainer_rule", 0), 0))
    high = int(_num(cand.get("a3_high", 0), 0))
    normal = int(_num(cand.get("a3", 0), 0))
    score = min(1.0, 0.20 + stars * 0.20 + trainer * 0.25 + high * 0.15 + normal * 0.05)
    if trainer: reasons.append("調教師判定○")
    if high: reasons.append("高勝率A3")
    if stars >= 2: reasons.append("強調教")
    return score, reasons, False


def rank_partners(df: pd.DataFrame, anchor_no: int | float, exclude_jirai: bool = True) -> pd.DataFrame:
    """Rank race-mates conditional on a selected training-first anchor.

    `partner_score` is a transparent Ver.3 ranking score (0-100), NOT a calibrated
    conditional place probability. A later walk-forward model may calibrate it.
    """
    x = df.copy().reset_index(drop=True)
    horse_no = pd.to_numeric(x.get("馬番"), errors="coerce")
    anchor_hit = x[horse_no.eq(float(anchor_no))]
    if anchor_hit.empty:
        raise ValueError(f"本命馬番 {anchor_no} が見つかりません")
    anchor = anchor_hit.iloc[0]

    place_pct = _percentile(x.get("MC複勝率", pd.Series(0.0, index=x.index)))
    final_pct = _percentile(x.get("final_nexus_prob", x.get("nexus_base_prob", pd.Series(0.0, index=x.index))))

    rows = []
    for i, cand in x.iterrows():
        if _num(cand.get("馬番"), -1) == float(anchor_no):
            continue
        dev, dev_r = _development_component(anchor, cand)
        ped, ped_r = _pedigree_component(anchor, cand)
        surf, surf_r = _surface_component(anchor, cand)
        train, train_r, is_jirai = _training_component(cand)
        ability = float(np.clip(0.65 * place_pct.iloc[i] + 0.35 * final_pct.iloc[i], 0.0, 1.0))
        score = 100.0 * (
            PARTNER_V3_WEIGHTS["development"] * dev
            + PARTNER_V3_WEIGHTS["pedigree"] * ped
            + PARTNER_V3_WEIGHTS["surface"] * surf
            + PARTNER_V3_WEIGHTS["training"] * train
            + PARTNER_V3_WEIGHTS["ability"] * ability
        )
        reasons = dev_r + ped_r + surf_r + train_r
        if not reasons:
            reasons = ["単体好走力を中心に評価"]
        rows.append({
            "馬番": cand.get("馬番"),
            "馬名": cand.get("馬名"),
            "Partner Score": round(float(score), 1),
            "展開連動": round(dev * 100, 0),
            "血統共有": round(ped * 100, 0),
            "馬場連動": round(surf * 100, 0),
            "調教状態": round(train * 100, 0),
            "単体好走力": round(ability * 100, 0),
            "地雷": bool(is_jirai),
            "理由": " / ".join(dict.fromkeys(reasons)),
            "MC複勝率": _num(cand.get("MC複勝率", 0)),
            "Final Nexus": _num(cand.get("final_nexus_prob", cand.get("nexus_base_prob", 0))),
        })
    out = pd.DataFrame(rows)
    if exclude_jirai and not out.empty:
        out = out[~out["地雷"]].copy()
    return out.sort_values(["Partner Score", "MC複勝率", "Final Nexus"], ascending=False).reset_index(drop=True)
