# Training history formal specification

## Nagori A3
- Definition: immediately previous race was ordinary A3 AND current race is 45-60 days later.
- 61-75 days: no Nagori A3 mark.
- 76-90 days: research candidate only; not part of the formal flag.
- 91+ days: no Nagori A3 mark.
- No direct star or Nexus probability bonus at this stage.

## Persistent history
`data/a3_history.csv` stores all race starts, not only A3 starts, so the application can identify the true immediately previous start rather than merely finding any A3 within the date window.

After updating `data/training_current.csv` locally, execute:

```bash
python scripts/update_a3_history.py
```

Then commit both `training_current.csv` and `a3_history.csv`.

## High-ROI trainer badge
Displayed only when `調教師判定` is positive for:
- 加藤士津八 (aliases such as 加藤志津 are normalized)
- 斎藤誠 (斉藤誠 alias normalized)
- 吉岡辰弥
- 森秀行

The badge is informational and does not double-count the trainer-rule star.
