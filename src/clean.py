"""Step 1 of the pipeline: turn any bank/wallet export (CSV or Excel) into one standard table.

Standard output columns:
    txn_id (text) | date (datetime) | description (text) | amount (positive number) | type ('debit' or 'credit')

Handles messy real-world exports:
  - bank name / account details / blank lines ABOVE the column headers (header row is found automatically)
  - comma, semicolon, tab or pipe separated files
  - UTF-8, UTF-16 and Windows (cp1252) text encodings
  - Excel files (.xlsx / .xls) as well as CSV
  - column names with extras, e.g. "Withdrawal Amount (PKR)" or "Txn Date"
  - amounts like "1,250.00", "PKR 1,250", "(500)", "500-", "1,250.00 Dr"
  - "Total" / "Closing balance" rows at the bottom (dropped)
  - whole lines wrapped in quotes ("Date,Description,Debit,...")
  - long descriptions split over two lines (joined back together)
"""
import csv
import hashlib
import io
from pathlib import Path

import pandas as pd

# True  = dates in your file are day-first, e.g. 05/07/2026 means 5 July (Pakistani banks)
# False = month-first, e.g. 07/05/2026 means 5 July
DAYFIRST = True

# Different banks name their columns differently. Add your bank's column
# names (in lowercase) to the right list if the script cannot find them.
COLUMN_ALIASES = {
    "date": ["date", "transaction date", "txn date", "tran date", "posting date", "post date",
             "value date", "booking date"],
    "description": ["description", "narration", "details", "particulars", "transaction details",
                    "transaction description", "remarks", "narrative", "memo", "merchant"],
    "amount": ["amount", "transaction amount", "txn amount", "amount (pkr)", "amount(pkr)"],
    "type": ["type", "dr/cr", "cr/dr", "transaction type", "txn type", "debit/credit"],
    "debit": ["debit", "withdrawal", "withdrawals", "debit amount", "withdrawal amount", "money out",
              "dr", "paid out"],
    "credit": ["credit", "deposit", "deposits", "credit amount", "deposit amount", "money in",
               "cr", "paid in"],
}

# Columns that must never be picked as amount/debit/credit, even if their name contains those words
_NEVER_AMOUNT = ("balance",)


def _match(column, key, exact_only=False):
    """Does this column name match one of the aliases for key?"""
    name = str(column).strip().lower()
    aliases = COLUMN_ALIASES[key]
    if name in aliases:
        return True
    if exact_only:
        return False
    if key in ("amount", "debit", "credit") and any(word in name for word in _NEVER_AMOUNT):
        return False
    # partial match, e.g. "withdrawal amount (pkr)" contains "withdrawal".
    # Very short aliases ("dr", "cr") only match exactly, so "address" never matches "dr".
    return any(len(a) >= 4 and a in name for a in aliases)


def _find_column(df, key):
    """Return the real column name in df that matches one of our aliases, or None.
    Exact names win over partial matches."""
    for exact_only in (True, False):
        for column in df.columns:
            if _match(column, key, exact_only):
                return column
    return None


def _decode(data):
    """Bytes -> text, trying the encodings banks actually use."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")  # never fails


def _find_header_row(rows, max_scan=60):
    """Index of the row that holds the column headers, or None.
    A header row has a date column plus a description or amount-type column."""
    for i, row in enumerate(rows[:max_scan]):
        cells = [str(c).strip() for c in row if str(c).strip()]
        if len(cells) < 3:
            continue
        has_date = any(_match(c, "date") for c in cells)
        has_other = any(_match(c, k) for c in cells for k in ("description", "amount", "debit", "credit"))
        if has_date and has_other:
            return i
    return None


def _unwrap(rows):
    """Some banks wrap each WHOLE line in quotes, e.g. "Date,Description,Debit".
    Then every row is one cell that still contains commas: split those cells again."""
    filled = [r for r in rows if any(str(c).strip() for c in r)]
    if filled and sum(len(r) == 1 and "," in r[0] for r in filled) >= 0.8 * len(filled):
        return [next(csv.reader([r[0]]), []) if r else [] for r in rows]
    return rows


def _merge_continuations(raw, date_col, desc_col):
    """Some statements split a long description over two lines:
        16 Jul 2026, VISA Purchase 497464 ESMART, 5,910.00, , 28,354.00
                   , POINT>BASEMENT 216        ,         , ,
    The second line has no date and no amounts. Join it onto the line above."""
    others = [c for c in raw.columns if c not in (date_col, desc_col)]
    merged = []
    for row in raw.to_dict("records"):
        is_continuation = (
            not str(row[date_col]).strip()
            and str(row[desc_col]).strip()
            and all(not str(row[c]).strip() for c in others)
        )
        if is_continuation and merged:
            merged[-1][desc_col] = f"{merged[-1][desc_col]} {row[desc_col]}".strip()
        else:
            merged.append(row)
    return pd.DataFrame(merged, columns=raw.columns, dtype=str)


def _read_table(source):
    """Read a CSV/Excel path or an uploaded file into a DataFrame of text,
    starting at the real header row."""
    name = str(getattr(source, "name", source)).lower()
    if hasattr(source, "getvalue"):          # Streamlit upload
        data = source.getvalue()
    elif hasattr(source, "read"):
        data = source.read()
    else:
        data = Path(source).read_bytes()

    if name.endswith((".xlsx", ".xls")):
        grid = pd.read_excel(io.BytesIO(data), header=None, dtype=str).fillna("")
        candidates = [grid.values.tolist()]
    else:
        text = _decode(data)
        candidates = [_unwrap(list(csv.reader(io.StringIO(text), delimiter=d))) for d in (",", ";", "\t", "|")]

    # Pick the separator whose header row has the most columns
    best_rows, best_idx, best_width = None, None, -1
    for rows in candidates:
        idx = _find_header_row(rows)
        if idx is not None and len(rows[idx]) > best_width:
            best_rows, best_idx, best_width = rows, idx, len(rows[idx])
    if best_rows is None:
        best_rows, best_idx = candidates[0], 0  # fall back: assume first row is the header

    header = [str(c).strip() for c in best_rows[best_idx]]
    columns, seen = [], {}
    for i, h in enumerate(header):  # make every header non-empty and unique
        h = h or f"column_{i + 1}"
        seen[h] = seen.get(h, -1) + 1
        columns.append(h if seen[h] == 0 else f"{h}_{seen[h]}")

    width = len(columns)
    body = [([str(c) for c in r] + [""] * width)[:width] for r in best_rows[best_idx + 1:]]
    body = [r for r in body if any(c.strip() for c in r)]  # drop blank lines
    return pd.DataFrame(body, columns=columns, dtype=str)


def _to_number(series):
    """'PKR 1,250.00' -> 1250.0   '(500)' -> -500.0   '500-' -> -500.0   '' or '-' -> NaN"""
    text = series.astype(str).str.strip()
    negative = (text.str.startswith("(") & text.str.endswith(")")) | text.str.endswith("-")
    text = text.str.replace(r"[^0-9.\-]", "", regex=True).str.rstrip("-")
    numbers = pd.to_numeric(text, errors="coerce")
    return numbers.where(~negative, -numbers.abs())


def _to_date(series):
    """Parse dates. ISO dates (2026-07-01, as Excel stores them) are always year-month-day;
    everything else follows DAYFIRST."""
    text = series.astype(str).str.strip()
    iso = text.str.match(r"^\d{4}-\d{1,2}-\d{1,2}")
    dates = pd.Series(pd.NaT, index=text.index, dtype="datetime64[ns]")
    if iso.any():
        dates[iso] = pd.to_datetime(text[iso].str[:10], format="%Y-%m-%d", errors="coerce")
    if (~iso).any():
        dates[~iso] = pd.to_datetime(text[~iso], dayfirst=DAYFIRST, errors="coerce")
    return dates


def clean_file(source):
    """Read one file (a path or an uploaded file) and return the standard table."""
    raw = _read_table(source)
    rows_in = len(raw)

    date_col = _find_column(raw, "date")
    desc_col = _find_column(raw, "description")
    if date_col is None or desc_col is None:
        raise ValueError(
            f"Could not find a date and/or description column. Columns found: {list(raw.columns)}. "
            "Add your column names to COLUMN_ALIASES in src/clean.py."
        )

    raw = _merge_continuations(raw, date_col, desc_col)

    out = pd.DataFrame()
    out["date"] = _to_date(raw[date_col])
    out["description"] = raw[desc_col].str.strip().str.replace(r"\s+", " ", regex=True)

    debit_col = _find_column(raw, "debit")
    credit_col = _find_column(raw, "credit")
    amount_col = _find_column(raw, "amount")
    type_col = _find_column(raw, "type")
    if amount_col in (debit_col, credit_col):  # e.g. "Debit Amount" matched both lists
        amount_col = None

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
    elif amount_col:  # layout C: one Amount column, signed (-500) or marked ("500 Dr")
        text = raw[amount_col].astype(str).str.lower()
        signed = _to_number(raw[amount_col])
        is_debit = (signed < 0) | text.str.contains(r"\bdr\b")
        out["amount"] = signed.abs()
        out["type"] = is_debit.map({True: "debit", False: "credit"})
    else:
        raise ValueError(
            f"Could not find amount columns. Columns found: {list(raw.columns)}. "
            "Add your column names to COLUMN_ALIASES in src/clean.py."
        )

    # Drop rows that are not real transactions (totals, opening balance, footer notes...)
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