# Runaway's Nexus Ver.1 — Streamlit Cloud Deploy Checklist

## Streamlit Cloud settings
- Main file path: `app.py`
- Python: 3.13 recommended (the packaged models were smoke-tested with Python 3.13 and the pinned scientific stack below)
- Repository root must contain `app.py` and `requirements.txt`

## Pinned model runtime
- pandas 2.2.3
- numpy 2.3.5
- scipy 1.17.0
- scikit-learn 1.8.0
- joblib 1.5.3

The bundled `joblib` models were successfully loaded with this stack.

## Smoke test completed
Using the bundled 2026-09-12 Nakayama 1R data:
- RaceDevelopment probability sum: 1.000000
- Nexus Base probability sum: 1.000000
- Pedigree Core + formal RaceDevelopment + Monte Carlo + Nexus Base all executed without error.

## External network note
Win odds are fetched at runtime from external public pages/APIs. If an upstream site blocks Cloud requests or changes its HTML/API, Nexus analysis still runs; only odds/VALUE may be unavailable.

## Current Training Radar rule
- ★ = Normal A3
- ★★ = High-win-rate A3 or Trainer Rule
- ★★★ = overlapping strong primary training rules
- Course and B3 are auxiliary badges and do not increase stars.
- Yoshioka Tatsuo stable exception: when Trainer Rule is positive, the Jirai-lap flag is retained for audit but not applied by Nexus. If Trainer Rule is not positive, Jirai applies normally.
