-- Personal Finance Tool: core analysis queries (SQLite)

-- Q1. Monthly totals: money in, money out, and what is left
SELECT strftime('%Y-%m', txn_date)                                   AS month,
       ROUND(SUM(CASE WHEN txn_type = 'credit' THEN amount END), 0)  AS income,
       ROUND(SUM(CASE WHEN txn_type = 'debit'  THEN amount END), 0)  AS spending,
       ROUND(SUM(CASE WHEN txn_type = 'credit' THEN amount ELSE -amount END), 0) AS net
FROM transactions
GROUP BY month
ORDER BY month;

-- Q2. Category share of total spending (all months)
SELECT c.category_name,
       ROUND(SUM(t.amount), 0) AS total_spent,
       ROUND(100.0 * SUM(t.amount) /
             (SELECT SUM(amount) FROM transactions WHERE txn_type = 'debit'), 1) AS pct_of_spending
FROM transactions t
JOIN categories c ON c.category_id = t.category_id
WHERE t.txn_type = 'debit'
GROUP BY c.category_name
ORDER BY total_spent DESC;

-- Q3. Trend: spending per category per month
SELECT txn_month, category_name, txn_count, total_spent
FROM v_monthly_category_spend
ORDER BY txn_month, total_spent DESC;

-- Q4. Budget variance: where did I go over budget?
SELECT txn_month, category_name, monthly_budget, total_spent, remaining, pct_used
FROM v_budget_vs_actual
ORDER BY txn_month, pct_used DESC;

-- Q5. Month-over-month change in total spending
WITH monthly AS (
    SELECT strftime('%Y-%m', txn_date) AS month, SUM(amount) AS spending
    FROM transactions
    WHERE txn_type = 'debit'
    GROUP BY month
)
SELECT month,
       ROUND(spending, 0)                                   AS spending,
       ROUND(LAG(spending) OVER (ORDER BY month), 0)        AS previous_month,
       ROUND(100.0 * (spending - LAG(spending) OVER (ORDER BY month))
             / LAG(spending) OVER (ORDER BY month), 1)      AS pct_change
FROM monthly
ORDER BY month;

-- Q6. Flagged anomalies, most extreme first
SELECT txn_date, description, category_name, amount, z_score
FROM v_transactions
WHERE is_anomaly = 1
ORDER BY z_score DESC;

-- Q7. Top 10 merchants by total spend
SELECT description, COUNT(*) AS times, ROUND(SUM(amount), 0) AS total_spent
FROM transactions
WHERE txn_type = 'debit'
GROUP BY description
ORDER BY total_spent DESC
LIMIT 10;