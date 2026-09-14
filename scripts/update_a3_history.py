from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "data" / "training_current.csv"
HISTORY = ROOT / "data" / "a3_history.csv"

POSITIVE = {"〇", "○", "◎", "★", "true", "1", "yes", "有", "あり"}


def positive(v) -> bool:
    if pd.isna(v):
        return False
    s = str(v).strip()
    return s in POSITIVE or s.lower() in POSITIVE


def current_to_history(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "race_date": pd.to_numeric(df.get("年月日"), errors="coerce").astype("Int64"),
        "venue": df.get("場所", pd.Series("", index=df.index)).astype(str).str.strip(),
        "race_no": pd.to_numeric(df.get("R"), errors="coerce").astype("Int64"),
        "horse_no": pd.to_numeric(df.get("馬番"), errors="coerce").astype("Int64"),
        "horse_name": df.get("馬名", pd.Series("", index=df.index)).astype(str).str.strip(),
        "horse_id": df.get("血統登録番号", pd.Series("", index=df.index)).astype(str).str.replace(r"\.0$", "", regex=True).str.strip(),
        "a3": df.get("A3LAP判定", pd.Series(False, index=df.index)).map(positive),
        "a3_high": df.get("A3高勝率Lap", pd.Series(False, index=df.index)).map(positive),
        "trainer_judge": df.get("調教師判定", pd.Series(False, index=df.index)).map(positive),
        "jirai": df.get("地雷ラップ判定", pd.Series(False, index=df.index)).map(positive),
    })


def main():
    cur = pd.read_csv(CURRENT, encoding="utf-8-sig")
    add = current_to_history(cur)
    add = add[pd.to_numeric(add["race_date"], errors="coerce").between(20000101, 20991231)]
    add = add[add["horse_name"].ne("")]
    if HISTORY.exists():
        hist = pd.read_csv(HISTORY, encoding="utf-8-sig")
    else:
        hist = pd.DataFrame(columns=add.columns)
    out = pd.concat([hist, add], ignore_index=True)
    out["race_date"] = pd.to_numeric(out["race_date"], errors="coerce")
    out = out[out["race_date"].between(20000101, 20991231)].copy()
    out["race_date"] = out["race_date"].astype(int)
    out["race_no"] = pd.to_numeric(out["race_no"], errors="coerce").fillna(0).astype(int)
    out["horse_no"] = pd.to_numeric(out["horse_no"], errors="coerce").fillna(0).astype(int)
    out = out.sort_values(["race_date", "venue", "race_no", "horse_no"])
    out = out.drop_duplicates(["race_date", "venue", "race_no", "horse_name"], keep="last")
    out.to_csv(HISTORY, index=False, encoding="utf-8-sig")
    print(f"A3 history updated: {len(out):,} rows / through {out['race_date'].max()}")


if __name__ == "__main__":
    main()
