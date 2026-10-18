"""Step 4 of the pipeline: store the results in a SQLite database."""
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("finance.db")
SCHEMA_PATH = Path("sql/schema.sql")
EXPORT_DIR = Path("powerbi")
EXPORTS = {"transactions.csv": "SELECT * FROM v_transactions",
           "categories.csv": "SELECT category_name FROM categories",
           "budgets.csv": "SELECT * FROM v_budgets"}


def connect(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))  # creates tables/views if missing
    return conn


def load(df, budgets_path="config/budgets.csv", db_path=DB_PATH):
    """Write categories, budgets and transactions. Safe to run again and again:
    existing transactions are updated (not duplicated), new ones are added."""
    budgets = pd.read_csv(budgets_path)
    budgets["category"] = budgets["category"].astype(str).str.strip()

    conn = connect(db_path)
    with conn:  # one all-or-nothing database transaction
        names = sorted(set(df["category"]) | set(budgets["category"]))
        conn.executemany("INSERT OR IGNORE INTO categories (category_name) VALUES (?)", [(n,) for n in names])
        ids = dict(conn.execute("SELECT category_name, category_id FROM categories"))

        conn.execute("DELETE FROM budgets")
        conn.executemany(
            "INSERT INTO budgets (category_id, monthly_budget) VALUES (?, ?)",
            [(ids[c], float(b)) for c, b in zip(budgets["category"], budgets["monthly_budget"])],
        )

        rows = [
            (r.txn_id, r.date.strftime("%Y-%m-%d"), r.description, float(r.amount), r.type,
             ids[r.category], int(r.is_anomaly), float(r.z_score))
            for r in df.itertuples()
        ]
        conn.executemany(
            """INSERT INTO transactions
                   (txn_id, txn_date, description, amount, txn_type, category_id, is_anomaly, z_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (txn_id) DO UPDATE SET
                   category_id = excluded.category_id,
                   is_anomaly  = excluded.is_anomaly,
                   z_score     = excluded.z_score""",
            rows,
        )
    total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()
    return total


def export_for_powerbi(db_path=DB_PATH, out_dir=EXPORT_DIR):
    """Write the tables Power BI needs as CSV files (the simple connection method)."""
    out_dir.mkdir(exist_ok=True)
    conn = connect(db_path)
    for filename, query in EXPORTS.items():
        pd.read_sql_query(query, conn).to_csv(out_dir / filename, index=False)
    conn.close()
    return [str(out_dir / name) for name in EXPORTS]