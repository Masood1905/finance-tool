"""Streamlit app: upload a statement, see categories, budget tracking and anomalies.

Run from the project root:  streamlit run app.py
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from anomalies import flag_anomalies  # noqa: E402
from categorize import categorize, load_rules, uncategorized_report  # noqa: E402
from clean import clean_file, combine  # noqa: E402

SAMPLE = ROOT / "data" / "raw" / "sample_transactions.csv"

st.set_page_config(page_title="Expense Intelligence Tool", layout="wide")
st.title("Personal Finance / Expense Intelligence Tool")

# ---------- Sidebar: inputs ----------
with st.sidebar:
    st.header("1. Your data")
    uploads = st.file_uploader("Upload statement file(s) (CSV or Excel)", type=["csv", "xlsx"], accept_multiple_files=True)
    use_sample = st.checkbox("Use sample data instead", value=not uploads, disabled=bool(uploads))
    st.header("2. Settings")
    z_threshold = st.slider("Anomaly sensitivity (standard deviations)", 1.0, 4.0, 2.0, 0.5)
    st.caption("Lower = more transactions flagged.")

sources = uploads if uploads else ([SAMPLE] if use_sample and SAMPLE.exists() else [])
if not sources:
    st.info("Upload a CSV in the sidebar, or tick 'Use sample data instead'.")
    st.stop()

# ---------- Run the pipeline ----------
try:
    df = combine([clean_file(s) for s in sources])
except Exception as error:  # show a readable message instead of a crash
    st.error(f"Could not read the file: {error}")
    st.stop()

df = categorize(df, load_rules(ROOT / "config" / "category_keywords.csv"))
df = flag_anomalies(df, z_threshold=z_threshold)
df["month"] = df["date"].dt.strftime("%Y-%m")
budgets = pd.read_csv(ROOT / "config" / "budgets.csv")

# ---------- Month filter ----------
months = sorted(df["month"].unique())
choice = st.selectbox("Month", ["All months"] + months, index=len(months))
view = df if choice == "All months" else df[df["month"] == choice]
n_months = len(months) if choice == "All months" else 1
debits = view[view["type"] == "debit"]

# ---------- Headline numbers ----------
spent = debits["amount"].sum()
income = view[view["type"] == "credit"]["amount"].sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total spent", f"Rs {spent:,.0f}")
c2.metric("Income", f"Rs {income:,.0f}")
c3.metric("Net (income - spent)", f"Rs {income - spent:,.0f}")
c4.metric("Anomalies flagged", int(view["is_anomaly"].sum()))

# ---------- Charts ----------
left, right = st.columns(2)
with left:
    st.subheader("Spending by category")
    by_category = debits.groupby("category")["amount"].sum().sort_values(ascending=False)
    st.bar_chart(by_category)
with right:
    st.subheader("Monthly spending trend")
    trend = df[df["type"] == "debit"].groupby("month")["amount"].sum()
    st.line_chart(trend)

# ---------- Budget vs actual ----------
st.subheader("Budget vs actual")
actual = debits.groupby("category")["amount"].sum().rename("spent").reset_index()
table = budgets.merge(actual, on="category", how="left").fillna({"spent": 0})
table["budget"] = table["monthly_budget"] * n_months
table["remaining"] = table["budget"] - table["spent"]
table["used_pct"] = (100 * table["spent"] / table["budget"]).round(1)
table["status"] = table["used_pct"].map(lambda p: "OVER BUDGET" if p > 100 else ("Warning" if p >= 80 else "OK"))
st.dataframe(
    table[["category", "budget", "spent", "remaining", "used_pct", "status"]].sort_values("used_pct", ascending=False),
    hide_index=True,
    column_config={
        "budget": st.column_config.NumberColumn("Budget (Rs)", format="%.0f"),
        "spent": st.column_config.NumberColumn("Spent (Rs)", format="%.0f"),
        "remaining": st.column_config.NumberColumn("Remaining (Rs)", format="%.0f"),
        "used_pct": st.column_config.ProgressColumn("Used %", format="%.0f%%", min_value=0, max_value=100),
    },
)
over = table[table["used_pct"] > 100]["category"].tolist()
if over:
    st.warning("Over budget: " + ", ".join(over))

# ---------- Anomalies ----------
st.subheader("Unusual transactions")
flagged = view[view["is_anomaly"] == 1].sort_values("z_score", ascending=False)
if flagged.empty:
    st.success("No unusual transactions in this period.")
else:
    st.dataframe(flagged[["date", "description", "category", "amount", "z_score"]],
                 hide_index=True,
                 column_config={"date": st.column_config.DateColumn("date")})

# ---------- Uncategorized ----------
missing = uncategorized_report(view)
if len(missing):
    with st.expander(f"Uncategorized descriptions ({len(missing)}) - add keywords for these"):
        st.dataframe(missing, hide_index=True)

# ---------- All transactions + download ----------
with st.expander("All transactions"):
    st.dataframe(view.drop(columns=["txn_id"]), hide_index=True,
                 column_config={"date": st.column_config.DateColumn("date")})
st.download_button("Download categorized data (CSV)", view.to_csv(index=False).encode("utf-8"),
                   file_name="transactions_categorized.csv", mime="text/csv")