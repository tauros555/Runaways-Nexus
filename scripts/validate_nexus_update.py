from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
training = ROOT / "data/training_current.csv"
a3 = ROOT / "data/a3_history.csv"
history = ROOT / "data/rd/history_seed_2020_2026.csv.gz"

errors = []

if training.exists():
    t = pd.read_csv(training, encoding="utf-8-sig", low_memory=False)
    req = {"年月日","場所","R","馬番","馬名","A3LAP判定","調教師判定","地雷ラップ判定","血統登録番号"}
    miss = req - set(t.columns)
    if miss: errors.append(f"training_current missing columns: {sorted(miss)}")
    if len(t) == 0: errors.append("training_current is empty")
    else:
        latest = pd.to_numeric(t["年月日"], errors="coerce").max()
        print(f"training_current: {len(t):,} rows / latest={int(latest)}")
else:
    errors.append("training_current.csv not found")

if a3.exists():
    h = pd.read_csv(a3, encoding="utf-8-sig", low_memory=False)
    dup = h.duplicated(["race_date","venue","race_no","horse_name"]).sum() if {"race_date","venue","race_no","horse_name"}.issubset(h.columns) else -1
    print(f"a3_history: {len(h):,} rows / duplicate keys={dup}")
    if dup > 0: errors.append(f"a3_history duplicate keys={dup}")
else:
    errors.append("a3_history.csv not found")

if history.exists():
    r = pd.read_csv(history, encoding="utf-8-sig", compression="gzip", low_memory=False)
    req = {"race_key","date","馬番","馬名","PCI","RPCI"}
    miss = req - set(r.columns)
    if miss: errors.append(f"history_seed missing columns: {sorted(miss)}")
    dup = r.duplicated(["race_key","馬番"]).sum() if {"race_key","馬番"}.issubset(r.columns) else -1
    latest = pd.to_numeric(r.get("date"), errors="coerce").max() if len(r) else None
    print(f"history_seed: {len(r):,} rows / latest={int(latest) if pd.notna(latest) else '-'} / duplicate keys={dup}")
    if dup > 0: errors.append(f"history_seed duplicate keys={dup}")
else:
    errors.append("history_seed_2020_2026.csv.gz not found")

if errors:
    print("VALIDATION FAILED")
    for e in errors: print(" -", e)
    raise SystemExit(1)
print("VALIDATION OK")
