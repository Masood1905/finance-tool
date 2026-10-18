"""Run the whole pipeline on every CSV in data/raw/.

Run from the project root:  python src/run_pipeline.py
"""
from pathlib import Path

from anomalies import flag_anomalies
from categorize import categorize, load_rules, uncategorized_report
from clean import clean_file, combine
from database import DB_PATH, export_for_powerbi, load

RAW_DIR = Path("data/raw")
OUT_CSV = Path("data/processed/transactions_categorized.csv")


def main():
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        raise SystemExit(f"No CSV files found in {RAW_DIR}/. Add a statement or run src/generate_sample_data.py")
    real_files = [f for f in files if not f.name.startswith("sample_")]
    if real_files and len(real_files) < len(files):
        print("Real statement found: ignoring the sample file.")
        files = real_files

    print("1) Cleaning")
    tables = []
    for f in files:
        print(f" {f.name}")
        tables.append(clean_file(f))
    df = combine(tables)

    print("2) Categorizing")
    df = categorize(df, load_rules())
    debits = df[df["type"] == "debit"]
    matched = (debits["category"] != "Uncategorized").mean() * 100
    print(f"  {matched:.1f}% of debit transactions matched a keyword")
    missing = uncategorized_report(df)
    if len(missing):
        print("  Not matched yet (add keywords for these in config/category_keywords.csv):")
        print(missing.to_string(index=False))

    print("3) Detecting anomalies")
    df = flag_anomalies(df)
    flagged = df[df["is_anomaly"] == 1].sort_values("z_score", ascending=False)
    print(f"  {len(flagged)} transactions flagged")
    if len(flagged):
        print(flagged[["date", "description", "category", "amount", "z_score"]].to_string(index=False))

    print("4) Saving")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    total_rows = load(df)
    print(f"  {OUT_CSV}  ({len(df)} rows)")
    print(f"  {DB_PATH}  ({total_rows} rows in transactions table)")
    for path in export_for_powerbi():
        print(f"  {path}")

    print("\nCheck these totals against your Excel pivot table:")
    print(f"  Transactions : {len(df)}")
    print(f"  Total debits : {debits['amount'].sum():,.2f}")
    print(f"  Total credits: {df[df['type'] == 'credit']['amount'].sum():,.2f}")


if __name__ == "__main__":
    main()