"""Step 3 of the pipeline: flag unusually large spending.

Method (z-score): inside each category, measure how many standard deviations
a transaction is above that category's average.
    z = (amount - category average) / category standard deviation
A transaction is flagged when z is greater than Z_THRESHOLD.
"""
import pandas as pd

Z_THRESHOLD = 2.0   # the "2 standard deviations" rule from the proposal
MIN_TXNS = 5        # categories with fewer debits than this are too small to judge


def flag_anomalies(df, z_threshold=Z_THRESHOLD, min_txns=MIN_TXNS):
    """Add 'z_score' and 'is_anomaly' (1/0) columns. Only debits are checked."""
    df = df.copy()
    df["z_score"] = 0.0
    df["is_anomaly"] = 0

    debits = df[df["type"] == "debit"]
    by_category = debits.groupby("category")["amount"]
    mean = by_category.transform("mean")
    std = by_category.transform("std")
    count = by_category.transform("count")

    usable = (count >= min_txns) & (std > 0)
    z = ((debits["amount"] - mean) / std).where(usable, 0.0)

    df.loc[debits.index, "z_score"] = z.round(2)
    df.loc[debits.index, "is_anomaly"] = (z > z_threshold).astype(int)
    return df