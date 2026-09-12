from __future__ import annotations
import numpy as np
import pandas as pd


def add_value_metrics(df: pd.DataFrame, odds_col: str = "単勝オッズ", prob_col: str = "final_nexus_prob") -> pd.DataFrame:
    """Add fair odds and market value metrics when win odds are available.

    VALUE = Nexus probability × market decimal odds.
    1.00 is break-even before takeout/estimation error; the UI should treat it
    as a ranking aid rather than an automatic betting rule.
    """
    x = df.copy()
    p = pd.to_numeric(x.get(prob_col), errors="coerce")
    odds = pd.to_numeric(x.get(odds_col), errors="coerce")
    x["Nexus適正オッズ"] = np.where(p > 0, 1.0 / p, np.nan)
    x["VALUE"] = p * odds
    return x
