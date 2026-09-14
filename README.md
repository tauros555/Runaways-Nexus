# Runaway's Nexus Ver.1 — Deploy Ready

Integrated Streamlit application combining:
- Training Radar
- Pedigree Core
- Formal RaceDevelopment models + Monte Carlo
- Nexus Base Probability
- Surface / Day Bias hooks
- Odds / VALUE hooks

Deploy with `app.py` as the Streamlit Cloud main file.
See `DEPLOY_CHECKLIST.md` before deployment.


## Partner Compatibility Ver.1
Race Analysis に「本命連動相手」を追加。
- 本命候補: 高勝率A3または調教師判定○、かつ実適用地雷なしを優先
- 本命は画面上で選択可能
- 相手評価: 展開連動35% / 血統条件共有20% / 馬場連動20% / 調教状態10% / 単体好走力15%
- 地雷ラップ馬は相手候補から除外可能（初期値ON）
- Partner ScoreはVer.1の相対順位であり、条件付き複勝確率ではない。Walk Forward検証後に校正予定。


## Partner Ver.2 Experimental
Candidate weights from 2026 chronological backtest: development 0.10, pedigree 0.00, surface 0.50, training 0.20, ability 0.20. Experimental only; market-residual ranking remains a research target and is not treated as calibrated probability.


## Partner Compatibility Ver.3 FORMAL

正式仕様：
- ◎本命：高勝率A3 または 調教師判定○、かつ有効地雷なしを優先。ユーザー変更可。
- Partner候補：◎本命を除く、地雷除外後の相手候補。
- Partner Score：単体好走力60% / 展開連動25% / 血統条件連動10% / 馬場連動5% / 調教加点0%。
- 調教0%は無視ではなく、本命選定で既に使用しているため二重加点しない設計。
- 市場本線：◎本命を除く非地雷候補の人気上位2頭。
- NEXUS連動穴：市場本線2頭を除いた候補のうちPartner Score最上位1頭。
- Partner Scoreは条件付き複勝確率ではなく相対順位。
- SmartRCは完全除外。
- 距離短縮・延長のコードは保持するが、再構築した暫定補正マスタはHoldoutで安定しなかったため正式版には同梱しない。正式マスタが無い場合は補正0へ安全にフォールバック。

## UI / Track Update 1
- JRA公式馬場情報を当日レースで自動取得（芝/ダート馬場状態・芝クッション値）。
- 芝クッション値とダート馬場状態は手動修正可能。取得失敗時は未指定のまま手動入力へフォールバック。
- 過去日レースには当日のJRA馬場情報を自動適用しない。
- Race Analysisの開催日・開催場・レース番号を1つのRACE SELECTORへ集約。
- FINAL NEXUS TOP 3直下にRaceDevelopment正式モデルの1角・最終角展開予想図を追加。

## Training Radar additions: Nagori A3 / High-ROI trainer badge

- `🟣 なごりA3`: the horse's immediately previous start was ordinary A3 and the current start is 45-60 days later.
  - This is stored/displayed as an independent feature. It does not increase training stars by itself.
  - `data/a3_history.csv` stores all starts needed to identify the immediately previous race.
  - After replacing `data/training_current.csv`, run `python scripts/update_a3_history.py` before committing so the history persists through Streamlit redeploys.
- `🏆 高回収厩舎`: displayed only when trainer rule is positive and the trainer is one of 加藤士津八 / 斎藤誠 / 吉岡辰弥 / 森秀行.
  - This badge does not add another training star because trainer rule is already a primary training signal.
  - 吉岡辰弥 + trainer rule positive keeps the existing Jirai override.
