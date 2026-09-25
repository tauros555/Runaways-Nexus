# Runaway's Nexus 自動更新（2026-09-25 現行）

## 配置
`Runaways_Nexus` 直下に `.git / app.py / scripts / data / tools` が同じ階層で存在する状態で使用します。

本番更新は次をダブルクリックします。

`★【これをクリック】UPDATE_NEXUS.bat`

`.git` が無い場合、BATはGit管理情報の復旧を試みます。作業中ファイルを意図的に上書きする処理ではありません。

## CSV更新手順
`data/inbox` に最新の以下を置きます。
- `DE*.CSV`
- `h.csv`
- `w.csv`
- `馬単位*.csv`
- `レースデータ*.csv`

その後 `★【これをクリック】UPDATE_NEXUS.bat` を実行します。
Excel再計算 → training_current → 前日追い → A3履歴 → RaceDevelopment履歴 → 検証 → Git commit/push を順に実行します。

## 調教判定表
実働テンプレート名は互換性維持のため以下のままです。

`tools/training/training_judgement_ver2_1.xlsx`

新様式で末尾列が増えていても、現在の更新処理は `メイン判定 A:CK` を `training_current.csv` 用に書き出します。CL以降はExcel内部計算・別管理用であり、既存A:CKの列順を変更しない限りこの出力仕様を維持します。

## 確認用
- `VERIFY_UPDATE_FILES.bat`: 最新アプリ構成・必要ファイルの存在確認のみ。
- `CHECK_UPDATE_NEXUS.bat`: Git pushなしでローカル更新処理を確認。

通常のCSV更新は `★【これをクリック】UPDATE_NEXUS.bat` だけでOKです。
