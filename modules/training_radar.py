from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pandas as pd

POSITIVE = {"〇", "○", "◎", "★", "true", "1", "yes", "有", "あり"}

HIGH_ROI_TRAINERS = {
    "加藤士津八": "加藤士津八",
    "加藤士津": "加藤士津八",
    "加藤志津": "加藤士津八",
    "斎藤誠": "斎藤誠",
    "斉藤誠": "斎藤誠",
    "吉岡辰弥": "吉岡辰弥",
    "森秀行": "森秀行",
}

NAGORI_MIN_DAYS = 45
NAGORI_MAX_DAYS = 60


def _positive(value) -> bool:
    if value is None:
        return False

    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass

    if isinstance(value, bool):
        return value

    s = str(value).strip()
    return s in POSITIVE or s.lower() in POSITIVE


def _normalize_high_roi_trainer(name: object) -> str:
    if name is None:
        return ""

    try:
        if pd.isna(name):
            return ""
    except (TypeError, ValueError):
        pass

    s = str(name).strip()
    if not s or s.lower() in {"nan", "none", "<na>"}:
        return ""

    for alias, canonical in HIGH_ROI_TRAINERS.items():
        if s.startswith(alias):
            return canonical
    return ""


def _add_nagori_a3(df: pd.DataFrame, history_path: str | Path | None) -> pd.DataFrame:
    out = df.copy()
    out["nagori_a3"] = False
    out["nagori_days"] = pd.NA
    out["prev_race_date"] = pd.NA
    out["prev_race_a3"] = False

    if not history_path:
        return out

    hp = Path(history_path)
    if not hp.exists():
        return out

    try:
        hist = pd.read_csv(hp, encoding="utf-8-sig")
    except Exception:
        return out

    required = {"race_date", "horse_name", "a3"}
    if not required.issubset(hist.columns):
        return out

    hist = hist.copy()
    hist["race_date"] = pd.to_numeric(hist["race_date"], errors="coerce")
    hist = hist[hist["race_date"].between(20000101, 20991231, inclusive="both")].copy()
    hist["horse_name"] = hist["horse_name"].astype(str).str.strip()
    hist["a3"] = hist["a3"].astype(str).str.lower().isin(
        ["true", "1", "yes", "○", "〇", "◎", "有", "あり"]
    )

    if "horse_id" in hist.columns:
        hist["horse_id"] = (
            hist["horse_id"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )

    by_name = {
        k: g.sort_values("race_date")
        for k, g in hist.groupby("horse_name", sort=False)
    }

    for idx, row in out.iterrows():
        cur_date = pd.to_numeric(row.get("年月日"), errors="coerce")
        if pd.isna(cur_date):
            continue

        name = str(row.get("馬名", "")).strip()
        if not name or name not in by_name:
            continue

        g = by_name[name]
        prev = g[g["race_date"] < int(cur_date)]
        if prev.empty:
            continue

        pr = prev.iloc[-1]
        prev_date = int(pr["race_date"])

        try:
            cur_dt = pd.to_datetime(str(int(cur_date)), format="%Y%m%d")
            prev_dt = pd.to_datetime(str(prev_date), format="%Y%m%d")
            days = int((cur_dt - prev_dt).days)
        except Exception:
            continue

        prev_a3 = bool(pr["a3"])
        out.at[idx, "prev_race_date"] = prev_date
        out.at[idx, "prev_race_a3"] = prev_a3
        out.at[idx, "nagori_days"] = days
        out.at[idx, "nagori_a3"] = bool(
            prev_a3 and NAGORI_MIN_DAYS <= days <= NAGORI_MAX_DAYS
        )

    return out


@dataclass(frozen=True)
class TrainingMark:
    stars: int
    label: str
    course_badge: bool
    b3_badge: bool
    jirai: bool


def _yoshioka_jirai_override(
    row: pd.Series,
    trainer_rule: bool,
    jirai_raw: bool,
) -> bool:
    trainer_name = str(row.get("調教師", "")).strip()
    if trainer_name.startswith("吉岡") and trainer_rule:
        return False
    return bool(jirai_raw)


def training_mark(row: pd.Series) -> TrainingMark:
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


def load_training(
    path: str | Path,
    history_path: str | Path | None = None,
) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")

    for c in ["年月日", "R", "馬番"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    if "血統登録番号" in df.columns:
        reg = (
            pd.to_numeric(df["血統登録番号"], errors="coerce")
            .astype("Int64")
            .astype("string")
        )
        short8 = reg.str.fullmatch(r"\d{8}", na=False)
        df["血統登録番号"] = reg.where(~short8, "20" + reg)

    valid_date = (
        df["年月日"].astype("string").str.fullmatch(r"\d{8}", na=False)
        if "年月日" in df.columns
        else pd.Series(False, index=df.index)
    )
    valid_r = (
        df["R"].between(1, 12, inclusive="both")
        if "R" in df.columns
        else pd.Series(False, index=df.index)
    )
    valid_horse = (
        df["馬番"].between(1, 28, inclusive="both")
        if "馬番" in df.columns
        else pd.Series(False, index=df.index)
    )
    valid_place = ~df.get(
        "場所",
        pd.Series("", index=df.index, dtype="object"),
    ).astype(str).isin(["", "0", "nan", "None", "<NA>"])

    df = df[valid_date & valid_r & valid_horse & valid_place].copy()

    marks = df.apply(training_mark, axis=1)
    df["training_stars"] = [m.stars for m in marks]
    df["training_level"] = [m.label for m in marks]
    df["course_badge"] = [m.course_badge for m in marks]
    df["b3_badge"] = [m.b3_badge for m in marks]
    df["jirai_badge"] = [m.jirai for m in marks]

    trainer_positive = df.get(
        "調教師判定",
        pd.Series(False, index=df.index, dtype="bool"),
    ).map(_positive)

    raw_jirai = df.get(
        "地雷ラップ判定",
        pd.Series(False, index=df.index, dtype="bool"),
    ).map(_positive)

    trainer_series = df.get(
        "調教師",
        pd.Series("", index=df.index, dtype="object"),
    )

    yoshioka = trainer_series.astype(str).str.strip().str.startswith("吉岡")

    df["吉岡地雷例外"] = yoshioka & trainer_positive & raw_jirai
    df["地雷適用"] = df["jirai_badge"]

    df["high_roi_trainer_name"] = trainer_series.map(
        _normalize_high_roi_trainer
    )
    df["high_roi_trainer"] = (
        trainer_positive & df["high_roi_trainer_name"].ne("")
    )

    df = _add_nagori_a3(df, history_path)

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
            nagori_count=("nagori_a3", "sum"),
            high_roi_trainer_count=("high_roi_trainer", "sum"),
        )
        .reset_index()
    )

    out["stars"] = out["max_stars"].map(
        lambda n: "★" * int(n) if n else "-"
    )

    return out.sort_values(
        ["max_stars", "strong_training_count", "good_training_count", "場所", "R"],
        ascending=[False, False, False, True, True],
    )


def race_horses(
    df: pd.DataFrame,
    venue: str,
    race_no: int,
) -> pd.DataFrame:
    x = df[(df["場所"] == venue) & (df["R"] == race_no)].copy()

    cols = [
        "馬番",
        "馬名",
        "父",
        "調教師",
        "ZI",
        "training_stars",
        "training_level",
        "A3LAP判定",
        "A3高勝率Lap",
        "調教師判定",
        "course_badge",
        "b3_badge",
        "jirai_badge",
        "地雷適用",
        "吉岡地雷例外",
        "high_roi_trainer",
        "high_roi_trainer_name",
        "nagori_a3",
        "nagori_days",
        "prev_race_date",
        "prev_race_a3",
        "コース判定",
        "B3LAP判定",
        "地雷ラップ判定",
    ]

    return x[[c for c in cols if c in x.columns]].sort_values("馬番")
