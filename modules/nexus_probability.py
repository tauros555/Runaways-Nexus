from __future__ import annotations
import numpy as np
import pandas as pd

NEXUS_V1_WEIGHTS = {
    "ped_distance": 0.258,
    "ped_turn": 0.327,
    "ped_slope": 0.137,
    "a3": 0.127,
    "a3_high": 0.028,
    "trainer_rule": 0.334,
    "jirai": -0.065,
}

TURF_SIRE_CUSHION_BETA = {
    ("サトノアラジン", "高"): 0.36,
    ("キタサンブラック", "低"): 0.30,
}

DIRT_SIRE_GOING_BETA = {
    ("パイロ", "重"): 0.40,
    ("マジェスティックウォリアー", "稍重"): 0.45,
    ("ロードカナロア", "不良"): 0.47,
    ("アジアエクスプレス", "稍重"): 0.13,
    ("ホッコータルマエ", "稍重"): 0.37,
    ("ディスクリートキャット", "重"): 0.25,
    ("ルーラーシップ", "良"): 0.20,
    ("ヴァンセンヌ", "良"): 0.41,
}

DAY_BIAS_WEIGHTS = {
    "芝": {"front_back": 0.10, "inside_outside": 0.03},
    "ダ": {"front_back": 0.08, "inside_outside": 0.02},
    "ダート": {"front_back": 0.08, "inside_outside": 0.02},
}


def _positive(v) -> int:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0
    return int(str(v).strip() in {"◎", "○", "〇", "◯", "1", "True", "TRUE", "true", "有", "あり"})


def add_training_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["a3"] = x.get("A3LAP判定", pd.Series(index=x.index)).map(_positive)
    x["a3_high"] = x.get("A3高勝率Lap", pd.Series(index=x.index)).map(_positive)
    x["trainer_rule"] = x.get("調教師判定", pd.Series(index=x.index)).map(_positive)
    x["jirai_raw"] = x.get("地雷ラップ判定", pd.Series(index=x.index)).map(_positive)

    # 吉岡厩舎例外：調教師判定○なら地雷ラップより調教師判定を優先する。
    # 調教師判定○でなければ地雷は通常どおり適用する。
    trainer_name = x.get("調教師", pd.Series("", index=x.index)).astype(str).str.strip()
    yoshioka_override = trainer_name.str.startswith("吉岡") & x["trainer_rule"].eq(1)
    x["yoshioka_jirai_override"] = yoshioka_override & x["jirai_raw"].eq(1)
    x["jirai"] = x["jirai_raw"].where(~yoshioka_override, 0)
    return x


def calculate_base_scores(df: pd.DataFrame) -> pd.DataFrame:
    x = add_training_features(df)
    p = pd.to_numeric(x["race_development_prob"], errors="coerce").fillna(0).clip(1e-9, 1.0)
    x["training_adjustment"] = (
        NEXUS_V1_WEIGHTS["a3"] * x["a3"]
        + NEXUS_V1_WEIGHTS["a3_high"] * x["a3_high"]
        + NEXUS_V1_WEIGHTS["trainer_rule"] * x["trainer_rule"]
        + NEXUS_V1_WEIGHTS["jirai"] * x["jirai"]
    )
    x["pedigree_adjustment"] = (
        NEXUS_V1_WEIGHTS["ped_distance"] * pd.to_numeric(x.get("ped_distance", 0), errors="coerce").fillna(0)
        + NEXUS_V1_WEIGHTS["ped_turn"] * pd.to_numeric(x.get("ped_turn", 0), errors="coerce").fillna(0)
        + NEXUS_V1_WEIGHTS["ped_slope"] * pd.to_numeric(x.get("ped_slope", 0), errors="coerce").fillna(0)
    )
    x["nexus_base_score"] = np.log(p) + x["training_adjustment"] + x["pedigree_adjustment"]
    ex = np.exp(x["nexus_base_score"] - x["nexus_base_score"].max())
    x["nexus_base_prob"] = ex / ex.sum()
    x["nexus_base_delta"] = x["nexus_base_prob"] - p
    return x


def get_surface_adjustment(surface: str, sire: str, cushion_band: str | None = None, going: str | None = None) -> float:
    if str(surface).strip() == "芝":
        return TURF_SIRE_CUSHION_BETA.get((str(sire).strip(), cushion_band), 0.0)
    return DIRT_SIRE_GOING_BETA.get((str(sire).strip(), going), 0.0)


def get_day_bias_adjustment(surface: str, front_back_fit: float = 0.0, inside_outside_fit: float = 0.0) -> float:
    w = DAY_BIAS_WEIGHTS.get(str(surface).strip(), {"front_back": 0.0, "inside_outside": 0.0})
    return w.get("front_back", 0.0) * float(front_back_fit or 0.0) + w.get("inside_outside", 0.0) * float(inside_outside_fit or 0.0)


def apply_surface_adjustment(df: pd.DataFrame, surface: str, going: str | None = None, cushion_band: str | None = None, front_back_fit_col: str | None = None, inside_outside_fit_col: str | None = None) -> pd.DataFrame:
    x = df.copy()
    sire_col = "父" if "父" in x.columns else "父馬名"
    x["sire_surface_adjustment"] = [get_surface_adjustment(surface, s, cushion_band, going) for s in x[sire_col]]
    fb = pd.to_numeric(x[front_back_fit_col], errors="coerce").fillna(0.0) if front_back_fit_col and front_back_fit_col in x.columns else pd.Series(0.0, index=x.index)
    io = pd.to_numeric(x[inside_outside_fit_col], errors="coerce").fillna(0.0) if inside_outside_fit_col and inside_outside_fit_col in x.columns else pd.Series(0.0, index=x.index)
    x["day_bias_adjustment"] = [get_day_bias_adjustment(surface, a, b) for a, b in zip(fb, io)]
    x["final_nexus_score"] = x["nexus_base_score"] + x["sire_surface_adjustment"] + x["day_bias_adjustment"]
    ex = np.exp(x["final_nexus_score"] - x["final_nexus_score"].max())
    x["final_nexus_prob"] = ex / ex.sum()
    return x
