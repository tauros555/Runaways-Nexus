from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pandas as pd

POSITIVE = {"〇", "○", "◎", "★", "true", "1", "yes", "有", "あり"}


def _positive(value) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, bool):
        return value
    s = str(value).strip()
    return s in POSITIVE or s.lower() in POSITIVE


@dataclass(frozen=True)
class TrainingMark:
    stars: int
    label: str
    course_badge: bool
    b3_badge: bool
    jirai: bool


def _yoshioka_jirai_override(row: pd.Series, trainer_rule: bool, jirai_raw: bool) -> bool:
    """吉岡厩舎の例外ルール。

    吉岡厩舎（現行データ上は「吉岡辰弥」）で調教師判定が○の場合、
    地雷ラップに該当していても地雷は採用しない。
    調教師判定が○でない場合は、通常どおり地雷を適用する。
    戻り値は「実際に適用する地雷フラグ」。
    """
    trainer_name = str(row.get("調教師", "")).strip()
    if trainer_name.startswith("吉岡") and trainer_rule:
        return False
    return bool(jirai_raw)


def training_mark(row: pd.Series) -> TrainingMark:
    """Nexus Ver.1 training display rule.

    ★1: ordinary A3
    ★2: high-win A3 OR trainer rule
    ★3: two or more primary strong signals overlap
    Course/B3 are auxiliary badges and never increase stars.
    Jirai is displayed separately and never increases stars.
    """
    a3 = _positive(row.get("A3LAP判定"))
    a3_high = _positive(row.get("A3高勝率Lap"))
    trainer = _positive(row.get("調教師判定"))
    course = _positive(row.get("コース判定"))
    b3 = _positive(row.get("B3LAP判定"))
    jirai_raw = _positive(row.get("地雷ラップ判定"))
    jirai = _yoshioka_jirai_override(row, trainer, jirai_raw)

    strong_count = int(a3_high) + int(trainer)
    if strong_count >= 2:
        stars = 3
        label = "Elite"
    elif a3_high or trainer:
        stars = 2
        label = "Strong"
    elif a3:
        stars = 1
        label = "A3"
    else:
        stars = 0
        label = "-"

    return TrainingMark(stars, label, course, b3, jirai)


def load_training(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    for c in ["年月日", "R", "馬番"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    if "血統登録番号" in df.columns:
        reg = pd.to_numeric(df["血統登録番号"], errors="coerce").astype("Int64").astype("string")
        short8 = reg.str.fullmatch(r"\d{8}", na=False)
        df["血統登録番号"] = reg.where(~short8, "20" + reg)
    # Keep only valid JRA race rows. The Excel-export CSV may contain helper/formula rows.
    valid_date = df["年月日"].astype("string").str.fullmatch(r"\d{8}", na=False) if "年月日" in df.columns else pd.Series(False, index=df.index)
    valid_r = df["R"].between(1, 12, inclusive="both") if "R" in df.columns else pd.Series(False, index=df.index)
    valid_horse = df["馬番"].between(1, 28, inclusive="both") if "馬番" in df.columns else pd.Series(False, index=df.index)
    valid_place = ~df.get("場所", pd.Series("", index=df.index)).astype(str).isin(["", "0", "nan", "None"])
    df = df[valid_date & valid_r & valid_horse & valid_place].copy()
    marks = df.apply(training_mark, axis=1)
    df = df.copy()
    df["training_stars"] = [m.stars for m in marks]
    df["training_level"] = [m.label for m in marks]
    df["course_badge"] = [m.course_badge for m in marks]
    df["b3_badge"] = [m.b3_badge for m in marks]
    df["jirai_badge"] = [m.jirai for m in marks]
    # 監査用：Excel原判定とNexusでの実適用を分離して保持する。
    trainer_positive = df.get("調教師判定", pd.Series(index=df.index)).map(_positive)
    raw_jirai = df.get("地雷ラップ判定", pd.Series(index=df.index)).map(_positive)
    yoshioka = df.get("調教師", pd.Series("", index=df.index)).astype(str).str.strip().str.startswith("吉岡")
    df["吉岡地雷例外"] = yoshioka & trainer_positive & raw_jirai
    df["地雷適用"] = df["jirai_badge"]
    return df


def summarize_races(df: pd.DataFrame) -> pd.DataFrame:
    keys = ["年月日", "場所", "R", "レース名", "芝・ダ", "距離"]
    out = (
        df.groupby(keys, dropna=False)
        .agg(
            max_stars=("training_stars", "max"),
            good_training_count=("training_stars", lambda s: int((s > 0).sum())),
            strong_training_count=("training_stars", lambda s: int((s >= 2).sum())),
            elite_count=("training_stars", lambda s: int((s >= 3).sum())),
            course_count=("course_badge", "sum"),
            b3_count=("b3_badge", "sum"),
            jirai_count=("jirai_badge", "sum"),
        )
        .reset_index()
    )
    out["stars"] = out["max_stars"].map(lambda n: "★" * int(n) if n else "-")
    return out.sort_values(["max_stars", "strong_training_count", "good_training_count", "場所", "R"], ascending=[False, False, False, True, True])


def race_horses(df: pd.DataFrame, venue: str, race_no: int) -> pd.DataFrame:
    x = df[(df["場所"] == venue) & (df["R"] == race_no)].copy()
    cols = [
        "馬番", "馬名", "父", "調教師", "ZI",
        "training_stars", "training_level", "A3LAP判定", "A3高勝率Lap", "調教師判定",
        "course_badge", "b3_badge", "jirai_badge", "地雷適用", "吉岡地雷例外", "コース判定", "B3LAP判定", "地雷ラップ判定",
    ]
    return x[[c for c in cols if c in x.columns]].sort_values("馬番")
