from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import pandas as pd

HISTORY_COLUMNS = [
    "race_key","date","year","場所","レース番号","芝・ダ","トラックコード","距離","頭数",
    "馬番","枠番","馬名","性別","騎手","騎手コード","斤量","確定着順","人気","単勝オッズ",
    "走破タイム(秒)","通過順位1角","通過順位2角","通過順位3角","通過順位4角","脚質",
    "上がり3Fタイム","PCI","RPCI","馬場状態","血統登録番号","父馬名",
]

HORSE_HEADERS = [
    "年","月","日","場所","レース番号","レース名","クラスコード","芝・ダ","トラックコード","トラックコード(JV)",
    "コーナー回数","距離","コース区分","馬場状態","天候","頭数","フルゲート頭数","1着本賞金","RPCI","PCI3",
    "基準タイム(秒)","年齢限定(競走種別コード)","レースID(IE)","レースID(新)","馬番","枠番","馬名","性別","年齢",
    "騎手","斤量","ブリンカー","確定着順","異常コード","着差タイム","人気","単勝オッズ","走破タイム(秒)","タイムS",
    "補正タイム","通過順位1角","通過順位2角","通過順位3角","通過順位4角","脚質","上がり3Fタイム","上り3F順位","Ave-3F",
    "PCI","-3F差","馬体重","調教師","増減","所属","血統登録番号","騎手コード","調教師コード","父馬名","母馬名",
    "母の父馬名","父タイプ","母父タイプ",
]

RACE_HEADERS = [
    "レースID(IE)","レースID(新)","年","月","日","場所","R","レース名","条件表記","クラスコード","グレードコード",
    "年齢限定(競走種別コード)","競走記号コード","重量コード","芝・ダート","距離","トラックコード","コース区分","コーナー回数",
    "1着本賞金","頭数","フルゲート頭数","天候","馬場状態","通過3F","通過4F","通過5F","上り5F","上り4F","上り3F",
    "前後3F差","前後4F差","前後5F差","1着入線タイム(秒)","全馬平均タイム(秒)","1-5着平均タイム(秒)","2-5着平均タイム(秒)",
    "PCI3","レースPCI","基準タイム(秒)","最速上3F","通過ラップ表記","上りラップ表記","単勝配当表記","Lap01","Lap02","Lap03",
    "Lap04","Lap05","Lap06","Lap07","Lap08","Lap09","Lap10","Lap11","Lap12","Lap13","Lap14","Lap15","Lap16","Lap17",
    "Lap18","Lap19","Lap20","Lap21","Lap22","Lap23","Lap24","Lap25","1コーナー位置","2コーナー位置","3コーナー位置",
    "4コーナー位置","単勝シェアの標準偏差","コースマーク","コースグループ名1",
]


def _read_headerless(path: Path, headers: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp932", header=None, dtype=str, low_memory=False)
    if df.shape[1] != len(headers):
        raise ValueError(f"{path.name}: 列数が想定と違います。実際={df.shape[1]} 想定={len(headers)}")
    df.columns = headers
    return df


def _clean(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip()


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def build_rows(horse_path: Path, race_path: Path) -> pd.DataFrame:
    horse = _read_headerless(horse_path, HORSE_HEADERS)
    race = _read_headerless(race_path, RACE_HEADERS)

    horse["race_key"] = _clean(horse["レースID(新)"]).str[:16]
    race["race_key"] = _clean(race["レースID(新)"])

    race_small = race[["race_key", "レースPCI", "馬場状態"]].drop_duplicates("race_key", keep="last")
    merged = horse.merge(race_small, on="race_key", how="left", suffixes=("", "_race"))

    year = _num(merged["年"])
    year4 = year.where(year >= 1000, year + 2000)
    date = (year4 * 10000 + _num(merged["月"]) * 100 + _num(merged["日"])).astype("Int64")

    out = pd.DataFrame({
        "race_key": _clean(merged["race_key"]),
        "date": date,
        "year": year4.astype("Int64"),
        "場所": _clean(merged["場所"]),
        "レース番号": _num(merged["レース番号"]).astype("Int64"),
        "芝・ダ": _clean(merged["芝・ダ"]).replace({"ダート": "ダ"}),
        "トラックコード": _num(merged["トラックコード"]).astype("Int64"),
        "距離": _num(merged["距離"]).astype("Int64"),
        "頭数": _num(merged["頭数"]).astype("Int64"),
        "馬番": _num(merged["馬番"]).astype("Int64"),
        "枠番": _num(merged["枠番"]).astype("Int64"),
        "馬名": _clean(merged["馬名"]),
        "性別": _clean(merged["性別"]),
        "騎手": _clean(merged["騎手"]),
        "騎手コード": _clean(merged["騎手コード"]),
        "斤量": _num(merged["斤量"]),
        "確定着順": _num(merged["確定着順"]).astype("Int64"),
        "人気": _num(merged["人気"]),
        "単勝オッズ": _num(merged["単勝オッズ"]),
        "走破タイム(秒)": _num(merged["走破タイム(秒)"]),
        "通過順位1角": _num(merged["通過順位1角"]).astype("Int64"),
        "通過順位2角": _num(merged["通過順位2角"]).astype("Int64"),
        "通過順位3角": _num(merged["通過順位3角"]).astype("Int64"),
        "通過順位4角": _num(merged["通過順位4角"]).astype("Int64"),
        "脚質": _clean(merged["脚質"]),
        "上がり3Fタイム": _num(merged["上がり3Fタイム"]),
        "PCI": _num(merged["PCI"]),
        "RPCI": _num(merged["レースPCI"]),
        "馬場状態": _clean(merged["馬場状態_race"]).where(_clean(merged["馬場状態_race"]).ne(""), _clean(merged["馬場状態"])),
        "血統登録番号": _clean(merged["血統登録番号"]),
        "父馬名": _clean(merged["父馬名"]),
    })

    out = out[out["race_key"].str.fullmatch(r"\d{16}", na=False)].copy()
    out = out[pd.to_numeric(out["馬番"], errors="coerce").between(1, 28, inclusive="both")].copy()
    out = out[HISTORY_COLUMNS]
    return out


def read_master(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    compression = "gzip" if path.suffix.lower() == ".gz" else None
    for enc in ("utf-8-sig", "cp932"):
        try:
            return pd.read_csv(path, encoding=enc, compression=compression, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("history", b"", 0, 1, f"{path} の文字コードを判定できません")


def backup_master(master: Path, backup_dir: Path) -> Path | None:
    if not master.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = ".csv.gz" if master.suffix.lower() == ".gz" else ".csv"
    dst = backup_dir / f"history_seed_{stamp}{suffix}"
    shutil.copy2(master, dst)
    return dst


def write_master(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compression = "gzip" if path.suffix.lower() == ".gz" else None
    df.to_csv(path, index=False, encoding="utf-8-sig", compression=compression)


def main() -> None:
    parser = argparse.ArgumentParser(description="TARGET馬単位＋レース単位からhistory_seedを差分更新")
    parser.add_argument("--horse", required=True, type=Path)
    parser.add_argument("--race", required=True, type=Path)
    parser.add_argument("--master", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path, default=Path("data/backup"))
    args = parser.parse_args()

    new_rows = build_rows(args.horse, args.race)
    master = read_master(args.master)
    for c in HISTORY_COLUMNS:
        if c not in master.columns:
            master[c] = pd.NA
    master = master[HISTORY_COLUMNS]

    old_count = len(master)
    incoming_count = len(new_rows)
    existing_keys = set(zip(master["race_key"].astype(str), pd.to_numeric(master["馬番"], errors="coerce").astype("Int64").astype(str)))
    incoming_keys = list(zip(new_rows["race_key"].astype(str), new_rows["馬番"].astype("Int64").astype(str)))
    new_unique_count = sum(k not in existing_keys for k in incoming_keys)

    backup = backup_master(args.master, args.backup_dir)

    out = pd.concat([master, new_rows], ignore_index=True)
    out["race_key"] = out["race_key"].astype(str).str.strip()
    out["馬番"] = pd.to_numeric(out["馬番"], errors="coerce").astype("Int64")
    out["date"] = pd.to_numeric(out["date"], errors="coerce").astype("Int64")
    out = out.drop_duplicates(["race_key", "馬番"], keep="last")
    out = out.sort_values(["date", "race_key", "馬番"], kind="stable").reset_index(drop=True)
    write_master(out, args.master)

    latest = int(pd.to_numeric(out["date"], errors="coerce").max()) if len(out) else 0
    print(f"history_seed updated: {old_count:,} -> {len(out):,} rows")
    print(f"input rows={incoming_count:,} / newly added keys={new_unique_count:,} / latest={latest}")
    if backup:
        print(f"backup: {backup}")


if __name__ == "__main__":
    main()
