-- Personal Finance Tool: database schema (SQLite)

CREATE TABLE IF NOT EXISTS categories (
    category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS budgets (
    budget_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id    INTEGER NOT NULL UNIQUE REFERENCES categories (category_id),
    monthly_budget REAL NOT NULL CHECK (monthly_budget >= 0)
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id      TEXT PRIMARY KEY,
    txn_date    TEXT NOT NULL,                 -- stored as YYYY-MM-DD
    description TEXT NOT NULL,
    amount      REAL NOT NULL CHECK (amount > 0),
    txn_type    TEXT NOT NULL CHECK (txn_type IN ('debit', 'credit')),
    category_id INTEGER NOT NULL REFERENCES categories (category_id),
    is_anomaly  INTEGER NOT NULL DEFAULT 0 CHECK (is_anomaly IN (0, 1)),
    z_score     REAL
);

CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions (txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions (category_id);

-- Views: saved queries that Power BI and the report can read like tables

DROP VIEW IF EXISTS v_transactions;
CREATE VIEW v_transactions AS
SELECT t.txn_id,
       t.txn_date,
       strftime('%Y-%m', t.txn_date) AS txn_month,
       t.description,
       t.amount,
       t.txn_type,
       c.category_name,
       t.is_anomaly,
       t.z_score
FROM transactions t
JOIN categories c ON c.category_id = t.category_id;

DROP VIEW IF EXISTS v_monthly_category_spend;
CREATE VIEW v_monthly_category_spend AS
SELECT strftime('%Y-%m', t.txn_date) AS txn_month,
       c.category_name,
       COUNT(*)                      AS txn_count,
       ROUND(SUM(t.amount), 2)       AS total_spent
FROM transactions t
JOIN categories c ON c.category_id = t.category_id
WHERE t.txn_type = 'debit'
GROUP BY txn_month, c.category_name;

DROP VIEW IF EXISTS v_budget_vs_actual;
CREATE VIEW v_budget_vs_actual AS
SELECT m.txn_month,
       c.category_name,
       b.monthly_budget,
       COALESCE(s.total_spent, 0)                                   AS total_spent,
       ROUND(b.monthly_budget - COALESCE(s.total_spent, 0), 2)      AS remaining,
       ROUND(100.0 * COALESCE(s.total_spent, 0) / b.monthly_budget, 1) AS pct_used
FROM (SELECT DISTINCT strftime('%Y-%m', txn_date) AS txn_month FROM transactions) m
CROSS JOIN budgets b
JOIN categories c ON c.category_id = b.category_id
LEFT JOIN v_monthly_category_spend s
       ON s.txn_month = m.txn_month AND s.category_name = c.category_name
WHERE b.monthly_budget > 0;

DROP VIEW IF EXISTS v_budgets;
CREATE VIEW v_budgets AS
SELECT c.category_name, b.monthly_budget
FROM budgets b
JOIN categories c ON c.category_id = b.category_id;