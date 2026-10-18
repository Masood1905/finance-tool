# Personal Finance / Expense Intelligence Tool

Automatically categorizes bank transactions, flags unusual spending, and tracks budget vs. actual expenses.

Built with Excel, Python, SQL (SQLite), Power BI, and Streamlit.

**Live app:** [Personal Finance / Expense Intelligence Tool](https://finance-tool-yn4qjsga4esrfdeccr57ny.streamlit.app/)

## Problem Statement

Managing personal finances manually can be time-consuming. Bank statements often contain unorganized transaction descriptions, making it difficult to understand spending patterns, identify unusual expenses, and determine whether spending is within budget.

This project addresses these challenges by automating transaction cleaning, expense categorization, anomaly detection, and budget analysis in one workflow.

## Project Benefits

- **Saves time:** Automates transaction processing and categorization.
- **Improves expense visibility:** Organizes transactions into meaningful spending categories.
- **Detects unusual spending:** Flags transactions that are unusually high compared with their category average.
- **Supports budget management:** Compares actual expenses with planned budgets and highlights overspending.
- **Enables data-driven decisions:** Uses dashboards to help users understand spending habits and identify opportunities to control expenses.

## How it works

1. `src/clean.py` standardizes bank CSV exports.
2. `src/categorize.py` assigns categories using `config/category_keywords.csv`.
3. `src/anomalies.py` flags transactions more than two standard deviations above the category average.
4. `src/database.py` loads processed data into SQLite using `sql/schema.sql`.
5. Power BI visualizes spending patterns and budget performance.
6. `app.py` provides a Streamlit interface for processing transaction uploads.

## Run it yourself

```bash
python -m venv venv
```

Activate the virtual environment on Windows:

```powershell
venv\Scripts\activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

Generate sample data and run the analysis pipeline:

```bash
python src/generate_sample_data.py
python src/run_pipeline.py
python src/run_queries.py
streamlit run app.py
```

## Key findings

- **Budget performance:** Groceries has the highest allocated budget overall but is also marked as over budget.
- **August spending:** Groceries ranks first in actual spending, followed by Food and Dining in second place and Shopping in third. However, Food and Dining ranks highest when comparing the budget allocations.
- **July spending:** Shopping has the highest actual spending by a substantial margin, despite having a relatively low budget allocation compared with other categories.
- **Anomaly detection:** The analysis identified a total of 7 anomalous transactions for further review.
- **Daily spending extremes:** July 3 recorded the highest daily spending, exceeding 160,000, while August 3 recorded the lowest, at just over 13,000.

*These findings are based on the project's sample analysis. Spending amounts are expressed in the currency used by the underlying transaction data.*

## Screenshots

### Power BI Dashboard

![Power BI Dashboard](screenshots/dashboard.png)

### Streamlit Application

![Streamlit Application](screenshots/streamlit-app.png)

## Technologies Used

- **Python & Pandas:** Data cleaning, categorization, and anomaly detection
- **SQL & SQLite:** Data storage and querying
- **Power BI:** Financial dashboard and visual analysis
- **Streamlit:** Interactive application interface
- **Excel:** Transaction review and analysis

## Data Privacy

Use synthetic or anonymized transaction data in this public repository. Do not upload real bank statements, account details, or confidential financial information.

## Project Structure

```text
finance-tool/
├── app.py
├── config/
├── data/
│   └── raw/
├── sql/
├── src/
├── screenshots/
│   ├── dashboard.png
│   └── streamlit-app.png
├── requirements.txt
└── README.md
```
