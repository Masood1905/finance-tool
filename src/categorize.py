"""Step 2 of the pipeline: give every transaction a category using keyword rules."""
import pandas as pd

INCOME = "Income"
UNCATEGORIZED = "Uncategorized"


def load_rules(path="config/category_keywords.csv"):
    """Read the keyword list. Longer keywords are checked first so that
    'youtube premium' wins over a shorter keyword such as 'youtube'."""
    rules = pd.read_csv(path)
    rules["keyword"] = rules["keyword"].astype(str).str.strip().str.lower()
    rules["category"] = rules["category"].astype(str).str.strip()
    rules = rules[rules["keyword"] != ""].drop_duplicates("keyword")
    rules = rules.sort_values("keyword", key=lambda s: s.str.len(), ascending=False)
    return list(zip(rules["keyword"], rules["category"]))


def categorize(df, rules):
    """Add a 'category' column. All credits are treated as Income."""
    def pick(description, kind):
        if kind == "credit":
            return INCOME
        text = description.lower()
        for keyword, category in rules:
            if keyword in text:
                return category
        return UNCATEGORIZED

    df = df.copy()
    df["category"] = [pick(d, k) for d, k in zip(df["description"], df["type"])]
    return df


def uncategorized_report(df, top=15):
    """The descriptions that matched no keyword, biggest total first.
    Use this list to decide which keywords to add next."""
    missing = df[df["category"] == UNCATEGORIZED]
    return (
        missing.groupby("description")["amount"].agg(times="count", total="sum")
        .sort_values("total", ascending=False).head(top).reset_index()
    )