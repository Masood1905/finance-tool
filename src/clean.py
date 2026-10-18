"""Step 1 of the pipeline: turn any bank/wallet CSV export into one standard table.

Standard output columns:
    txn_id (text) | date (datetime) | description (text) | amount (positive number) | type ('debit' or 'credit')
"""
import hashlib
import re

import pandas as pd

# True  = dates in your file are day-first, e.g. 05/07/2026 means 5 July (Pakistani banks)
# False = month-first, e.g. 07/05/2026 means 5 July
DAYFIRST = True

# Different banks name their columns differently. Add your bank's column
# names (in lowercase) to the right list if the script cannot find them.
COLUMN_ALIASES = {
    "date": ["date", "transaction date", "txn date", "posting date", "value date", "booking date"],
    "description": ["description", "narration", "details", "particulars", "transaction details", "remarks"],
    "amount": ["amount", "transaction amount", "amount (pkr)", "amount(pkr)"],
    "type": ["type", "dr/cr", "cr/dr", "transaction type"],
    "debit": ["debit", "withdrawal", "withdrawals", "debit amount", "money out"],
    "credit": ["credit", "deposit", "deposits", "credit amount", "money in"],
}


def _find_column(df, key):
    """Return the real column name in df that matches one of our aliases, or None."""
    lookup = {str(c).strip().lower(): c for c in df.columns}
    for alias in COLUMN_ALIASES[key]:
        if alias in lookup:
            return lookup[alias]
    return None


def _to_number(series):
    """'PKR 1,250.00' -> 1250.0   '(500)' -> -500.0   '' -> NaN"""
    text = series.astype(str).str.strip()
    negative = text.str.startswith("(") & text.str.endswith(")")
    text = text.str.replace(r"[^0-9.\-]", "", regex=True)
    numbers = pd.to_numeric(text, errors="coerce")
    return numbers.where(~negative, -numbers.abs())


def clean_file(source):
    """Read one CSV (a path or an uploaded file) and return the standard table."""
    raw = pd.read_csv(source, dtype=str, keep_default_na=False)
    rows_in = len(raw)

    date_col = _find_column(raw, "date")
    desc_col = _find_column(raw, "description")
    if date_col is None or desc_col is None:
        raise ValueError(
            f"Could not find a date and/or description column. Columns found: {list(raw.columns)}. "
            "Add your column names to COLUMN_ALIASES in src/clean.py."
        )

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(raw[date_col].str.strip(), dayfirst=DAYFIRST, errors="coerce")
    out["description"] = raw[desc_col].str.strip().str.replace(r"\s+", " ", regex=True)

    amount_col = _find_column(raw, "amount")
    type_col = _find_column(raw, "type")
    debit_col = _find_column(raw, "debit")
    credit_col = _find_column(raw, "credit")

    if debit_col and credit_col:  # layout A: separate Debit and Credit columns
        debit = _to_number(raw[debit_col]).fillna(0).abs()
        credit = _to_number(raw[credit_col]).fillna(0).abs()
        out["amount"] = debit.where(debit > 0, credit)
        out["type"] = (debit > 0).map({True: "debit", False: "credit"})
    elif amount_col and type_col:  # layout B: Amount column + DR/CR column
        out["amount"] = _to_number(raw[amount_col]).abs()
        kind = raw[type_col].str.strip().str.lower()
        is_debit = kind.str.startswith(("d", "w")) | kind.str.contains("out|purchase|payment")
        out["type"] = is_debit.map({True: "debit", False: "credit"})
    elif amount_col:  # layout C: one signed Amount column (negative = money out)
        signed = _to_number(raw[amount_col])
        out["amount"] = signed.abs()
        out["type"] = (signed < 0).map({True: "debit", False: "credit"})
    else:
        raise ValueError(
            f"Could not find amount columns. Columns found: {list(raw.columns)}. "
            "Add your column names to COLUMN_ALIASES in src/clean.py."
        )

    # Drop rows that are not real transactions (blank lines, totals, opening balance...)
    out = out.dropna(subset=["date", "amount"])
    out = out[(out["amount"] > 0) & (out["description"] != "")]
    out = out.sort_values("date", kind="stable").reset_index(drop=True)

    # A stable ID per transaction. 'occurrence' keeps two genuinely identical
    # transactions on the same day (e.g. two Rs 300 rides) as separate rows,
    # while the same statement loaded twice still produces the same IDs.
    key_cols = ["date", "description", "amount", "type"]
    occurrence = out.groupby(key_cols).cumcount()
    raw_key = (
        out["date"].dt.strftime("%Y-%m-%d") + "|" + out["description"].str.lower() + "|"
        + out["amount"].round(2).astype(str) + "|" + out["type"] + "|" + occurrence.astype(str)
    )
    out.insert(0, "txn_id", raw_key.map(lambda s: hashlib.sha1(s.encode()).hexdigest()[:16]))

    print(f"  cleaned: {rows_in} rows in -> {len(out)} transactions kept ({rows_in - len(out)} dropped)")
    return out


def combine(tables):
    """Stack several cleaned files and remove transactions that appear in more than one file."""
    combined = pd.concat(tables, ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset="txn_id").sort_values("date", kind="stable")
    if before != len(combined):
        print(f"  removed {before - len(combined)} duplicate transactions from overlapping files")
    return combined.reset_index(drop=True)