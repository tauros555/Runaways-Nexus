# V2 デバッグ版の使い方

## まず確認
このZIPの「nexus_auto_update」フォルダそのものを別の場所で実行しないでください。
フォルダの**中身**を既存の `Runaways-Nexus` リポジトリ直下へコピーします。

正しい配置例:

Runaways-Nexus/
  .git/
  app.py
  UPDATE_NEXUS.bat
  CHECK_UPDATE_NEXUS.bat
  config/
  scripts/
  tools/
  data/

## 初回テスト
まず `CHECK_UPDATE_NEXUS.bat` をダブルクリックしてください。
Git pull / commit / push はしませんが、Excel貼付・CSV生成・履歴更新まではローカルで実行します。

失敗した場合:
- ウィンドウは閉じません
- リポジトリ直下の `update_nexus.log` に原因が残ります

`update_nexus.log` をChatGPTへ貼り付ければ、停止箇所を特定できます。

## 本番
ローカルテストが成功したら `UPDATE_NEXUS.bat` をダブルクリックします。
Git pull → データ更新 → Git commit → push まで実行します。
