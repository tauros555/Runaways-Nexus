from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

HEADERS = [
"年月日","場所","R","馬番","レース名","芝・ダ","距離","馬名","性別","騎手","調教師","所属","父","芝・ダ","コースID","所属",
"日にち判定","前日判定","水曜日判定","木曜日判定","先週の土曜日判定","先週の日曜日判定","2w前の土曜日判定","2w前の日曜日判定",
"坂2w前 土 TIME1","坂2w前 土 LAP1","坂2w前 土 LAP2","坂2w前 日 TIME1","坂2w前 日 LAP1","坂2w前 日 LAP2",
"坂1w前 土 TIME1","坂1w前 土 LAP1","坂1w前 土 LAP2","坂1w前 日 TIME1","坂1w前 日 LAP1","坂1w前 日 LAP2",
" 坂 水 TIME1"," 坂 水 LAP1"," 坂 水 LAP2"," 坂 水 LAP3"," 坂 水 LAP4"," 坂 木 TIME1"," 坂 木 LAP1"," 坂 木 LAP2"," 坂 木 LAP3"," 坂 木 LAP4"," 坂 前日 TIME1",
"ウ2w前 土 １F","ウ2w前 日 １F","ウ1w前 土 １F","ウ1w前 土 5F","ウ1w前 日 １F","ウ1w前 日 5F",
"ウ 水 1F","ウ 水 4F","ウ 水 5F","ウ 水 6F","ウ 木 1F","ウ 木 4F","ウ 木 5F","ウ 木 6F","調教師判定",
"ウ 水1F","ウ 木1F","ウ 1F判定","ウ 前日 5F","水曜日A3","木曜日A3","A3LAP判定","水曜日B3","木曜日B3","B3LAP判定",
"前日坂路時計","前日坂路TIME１判定","水曜坂路爆速","木曜坂路爆速","坂路爆速判定","水曜地雷ラップ","木曜地雷ラップ","地雷ラップ判定",
"コース判定","A3高勝率Lap","本命候補判定","相手候補判定","ZI","脚質","枠","レースID","血統登録番号"
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    df = pd.read_csv(args.raw, encoding="utf-8-sig", header=None, dtype=object, low_memory=False)
    if df.shape[1] < len(HEADERS):
        raise ValueError(f"メイン判定の出力列が不足しています: {df.shape[1]} < {len(HEADERS)}")
    df = df.iloc[:, :len(HEADERS)].copy()
    # Excel側の1行目は判定表の見出しなので捨て、Nexus正本ヘッダーへ置換。
    df = df.iloc[1:].copy()
    df.columns = HEADERS

    date = pd.to_numeric(df["年月日"], errors="coerce")
    race = pd.to_numeric(df["R"], errors="coerce")
    horse = pd.to_numeric(df["馬番"], errors="coerce")
    valid = date.between(20000101, 20991231, inclusive="both") & race.between(1, 12, inclusive="both") & horse.between(1, 28, inclusive="both")
    df = df[valid].copy()
    df = df.sort_values(["年月日", "場所", "R", "馬番"], kind="stable")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"training_current updated: {len(df):,} rows / latest={int(pd.to_numeric(df['年月日'], errors='coerce').max())}")


if __name__ == "__main__":
    main()
