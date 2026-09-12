# Runaway's Nexus UI / Track Update 1

1. JRA馬場情報自動取得
   - SireAnalyzer Ver7.2の取得方式をNexusへ移植。
   - 当日（Asia/Tokyo）の選択レースのみ自動適用。
   - 芝: JRAクッション値を取得し、Nexus 3帯へ自動変換（低 <= 9.0 / 中 9.1-9.5 / 高 >= 9.6）。
   - ダート: JRA公式の良/稍重/重/不良を自動設定。
   - 手動修正・公式値へのリセットを維持。
   - 自動取得失敗時は未指定のまま手動設定可能。

2. Race Selector
   - 開催日 / 開催場 / レース番号を1つの枠・1行に統合。

3. 展開予想図
   - FINAL NEXUS TOP 3直下へ配置。
   - RaceDevelopmentの `render_route_grid` を再利用。
   - 1角: PredFirstRank / 初角ゾーン / 初角進路
   - 最終角: Pred4ScenarioRank / 最終角ゾーン / 最終角進路

4. Streamlit Cloud依存
   - requirements.txt: selenium>=4.20,<5.0
   - packages.txt: chromium / chromium-driver
