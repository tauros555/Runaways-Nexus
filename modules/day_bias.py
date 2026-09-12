from __future__ import annotations
import numpy as np
import pandas as pd

STYLE_SCORE = {
    "逃げ": 1.0,
    "逃げ候補": 0.85,
    "先行": 0.60,
    "中団": 0.0,
    "差し": -0.60,
    "追込": -1.0,
}
LANE_SCORE = {"内": 1.0, "中": 0.0, "外": -1.0}


def _surface_key(v: str) -> str:
    return "芝" if str(v).strip() == "芝" else "ダ"


def estimate_same_day_bias(history: pd.DataFrame, date: int, place: str, surface: str, current_race_no: int) -> dict:
    """Past-only day bias from completed earlier races at same venue/surface.

    front_back_bias: +1 front-favoring, -1 closer-favoring.
    inside_outside_bias: +1 inside-favoring, -1 outside-favoring.
    This uses top-3 finishers' actual 4-corner position and gate location relative
    to the field, centered against the field distribution for each completed race.
    """
    h = history.copy()
    surf = _surface_key(surface)
    h_date = pd.to_numeric(h.get("date"), errors="coerce")
    h_r = pd.to_numeric(h.get("レース番号"), errors="coerce")
    h_surf = h.get("芝・ダ", pd.Series(index=h.index, dtype=object)).astype(str).map(_surface_key)
    z = h[(h_date == int(date)) & (h["場所"].astype(str) == str(place)) & (h_surf == surf) & (h_r < int(current_race_no))].copy()
    if z.empty:
        return {
            "front_back_bias": 0.0,
            "inside_outside_bias": 0.0,
            "sample_races": 0,
            "source": "NO_PRIOR_RACES",
            "label_fb": "フラット",
            "label_io": "フラット",
        }

    race_signals = []
    for _, g in z.groupby("race_key"):
        n = len(g)
        if n < 4:
            continue
        fin = pd.to_numeric(g["確定着順"], errors="coerce")
        r4 = pd.to_numeric(g.get("通過順位4角"), errors="coerce")
        gate = pd.to_numeric(g.get("馬番"), errors="coerce")
        top = fin.between(1, 3)
        if top.sum() < 2:
            continue
        denom = max(n - 1, 1)
        # +1 front, -1 rear. Compare top3 with whole field baseline.
        pos_score = 1.0 - 2.0 * ((r4 - 1.0) / denom)
        gate_score = 1.0 - 2.0 * ((gate - 1.0) / denom)  # +1 inside, -1 outside
        fb = float(pos_score[top].mean() - pos_score.mean()) if pos_score.notna().sum() else 0.0
        io = float(gate_score[top].mean() - gate_score.mean()) if gate_score.notna().sum() else 0.0
        race_signals.append((np.clip(fb * 2.0, -1, 1), np.clip(io * 2.0, -1, 1)))

    if not race_signals:
        return {
            "front_back_bias": 0.0,
            "inside_outside_bias": 0.0,
            "sample_races": 0,
            "source": "NO_VALID_PRIOR_RACES",
            "label_fb": "フラット",
            "label_io": "フラット",
        }

    fb = float(np.clip(np.mean([x[0] for x in race_signals]), -1, 1))
    io = float(np.clip(np.mean([x[1] for x in race_signals]), -1, 1))

    def fb_label(v):
        if v >= .35: return "前有利"
        if v >= .15: return "やや前有利"
        if v <= -.35: return "差し有利"
        if v <= -.15: return "やや差し有利"
        return "フラット"

    def io_label(v):
        if v >= .35: return "内有利"
        if v >= .15: return "やや内有利"
        if v <= -.35: return "外有利"
        if v <= -.15: return "やや外有利"
        return "フラット"

    return {
        "front_back_bias": fb,
        "inside_outside_bias": io,
        "sample_races": len(race_signals),
        "source": "AUTO_PAST_ONLY",
        "label_fb": fb_label(fb),
        "label_io": io_label(io),
    }


def add_bias_fit(df: pd.DataFrame, front_back_bias: float, inside_outside_bias: float) -> pd.DataFrame:
    x = df.copy()
    style = x.get("今回想定脚質", pd.Series(index=x.index, dtype=object)).astype(str).map(STYLE_SCORE).fillna(0.0)
    lane = x.get("最終角進路", pd.Series(index=x.index, dtype=object)).astype(str).map(LANE_SCORE).fillna(0.0)
    x["front_back_fit"] = np.clip(float(front_back_bias), -1, 1) * style
    x["inside_outside_fit"] = np.clip(float(inside_outside_bias), -1, 1) * lane
    return x
