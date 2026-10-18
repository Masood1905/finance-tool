"""Run every query in sql/queries.sql and print the results.

Run from the project root:  python src/run_queries.py
Save the output to a file:  python src/run_queries.py > query_results.txt
"""
import sqlite3
from pathlib import Path

import pandas as pd

from database import DB_PATH

pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 100)
pd.set_option("display.max_colwidth", 60)

conn = sqlite3.connect(DB_PATH)
for block in Path("sql/queries.sql").read_text(encoding="utf-8").split(";"):
    lines = [line for line in block.strip().splitlines() if line.strip()]
    titles = [line[2:].strip() for line in lines if line.startswith("--")]
    sql = "\n".join(line for line in lines if not line.startswith("--"))
    if not sql.strip():
        continue
    print("\n" + "=" * 80)
    print(" ".join(t for t in titles if t.startswith("Q")) or "Query")
    print("=" * 80)
    result = pd.read_sql_query(sql, conn)
    print(result.to_string(index=False) if len(result) else "(no rows)")
conn.close()