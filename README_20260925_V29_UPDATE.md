# Runaway's Nexus ver2.9 current specification (2026-09-25)

## Racecard role display
The UI uses only the flame emoji for role display.
- `単🔥` = head / win-probability type
- `軸` = axis / in-the-money reliability type
- `紐` = opponent type
- `補` = watch / supplementary type
- combinations: `単🔥・軸`, `紐・補`, `複・紐`

`🟢` and `🔵` are not used in the application display.
Course roles are explanatory metadata and do not receive a fixed score bonus. Win-value is evaluated separately after odds are available.

## ver2.9 redesigned course rules
- 東京芝1800: 美浦 AND 前週土日坂路TIME1<58 AND 当週W1F<12 -> `単🔥・軸`
- 中京ダ1200: 栗東 AND same-day 当週坂路TIME1<56 AND LAP1<13 AND LAP2>13 (Wed OR Thu) -> `単🔥`
- 福島ダ1150: 栗東 AND 前週土日坂路あり -> `軸`
- 阪神芝1400: 栗東 AND 前週土日坂路TIME1<56 -> `紐`
- 中京ダ1900: removed from normal course judgement.

## Current formal Crown policy
- Keep all current trainer Crown rules.
- Course-training Crowns: only 3 rules remain:
  1. 東京ダ1400 栗東W
  2. 中山芝1200 栗東
  3. 中山芝1200 美浦
- Training judgement ○ x M: only `母母父 = 地-極-極` remains.
- All Course judgement ○ x M Crowns are removed.
- Other former course Crowns are removed.
- Crown hits continue to appear on the top screen.

## Training workbook
The workbook is managed separately. The updater continues to use:
`tools/training/training_judgement_ver2_1.xlsx`
The app-side course-role/Crown logic does not require the workbook to contain Crown or M judgement columns.
