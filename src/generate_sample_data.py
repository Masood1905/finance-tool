"""Create 3 months of realistic FAKE transactions so the whole pipeline
can be built and tested before (or instead of) using real bank data.

Run from the project root:  python src/generate_sample_data.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)  # same "random" data every run, so results are reproducible

OUT = Path("data/raw/sample_transactions.csv")
START, END = date(2026, 7, 1), date(2026, 9, 30)

# (description, min amount, max amount, roughly how many times per month)
VARIABLE = [
    ("FOODPANDA ORDER ISLAMABAD", 600, 2200, 8),
    ("KFC F-10 ISLAMABAD", 900, 2500, 2),
    ("CHAAYE KHANA F-6", 700, 1800, 2),
    ("CAREEM RIDE", 250, 900, 10),
    ("INDRIVE TRIP", 200, 700, 6),
    ("PSO FUEL STATION G-9", 2000, 5000, 3),
    ("IMTIAZ SUPER MARKET", 3000, 9000, 3),
    ("AL-FATAH GROCERY", 1500, 5000, 2),
    ("DARAZ.PK ONLINE", 800, 6000, 3),
    ("KHAADI CENTAURUS MALL", 3000, 8000, 1),
    ("SHIFA PHARMACY", 400, 2500, 2),
    ("CINEPAX TICKETS", 900, 2400, 2),
    ("ATM CASH WITHDRAWAL", 2000, 10000, 2),
    ("EASYPAISA TRANSFER TO 0300XXXXXXX", 500, 5000, 2),
    ("POS PURCHASE 4471 MISC STORE", 300, 3000, 2),  # deliberately matches no keyword
]

# (day of month, description, min, max, DR/CR) - happens once every month
MONTHLY = [
    (1, "SALARY CREDIT ABC PVT LTD", 95000, 95000, "CR"),
    (4, "PTCL BROADBAND BILL", 3500, 3500, "DR"),
    (7, "IESCO ELECTRICITY BILL", 8000, 15000, "DR"),
    (9, "SNGPL GAS BILL", 1200, 2500, "DR"),
    (12, "JAZZ MONTHLY PACKAGE", 1500, 1500, "DR"),
    (15, "NETFLIX.COM", 1100, 1100, "DR"),
    (15, "SPOTIFY PREMIUM", 349, 349, "DR"),
    (20, "YOUTUBE PREMIUM", 479, 479, "DR"),
]

# Unusually large transactions the anomaly detector should catch
ANOMALIES = [
    (date(2026, 7, 19), "DARAZ.PK ONLINE", 48000),
    (date(2026, 8, 11), "FOODPANDA ORDER ISLAMABAD", 9500),
    (date(2026, 9, 5), "CAREEM RIDE", 6200),
    (date(2026, 9, 22), "IMTIAZ SUPER MARKET", 31000),
]

rows = []
all_days = [START + timedelta(days=i) for i in range((END - START).days + 1)]
months = sorted({(d.year, d.month) for d in all_days})

for year, month in months:
    days = [d for d in all_days if (d.year, d.month) == (year, month)]
    for desc, low, high, per_month in VARIABLE:
        for _ in range(per_month + random.choice([-1, 0, 0, 1])):
            rows.append((random.choice(days), desc, random.randint(low, high), "DR"))
    for day, desc, low, high, kind in MONTHLY:
        rows.append((date(year, month, day), desc, random.randint(low, high), kind))

rows += [(d, desc, amount, "DR") for d, desc, amount in ANOMALIES]
rows.sort(key=lambda r: r[0])

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Description", "Amount", "Type"])
    for d, desc, amount, kind in rows:
        writer.writerow([d.strftime("%d/%m/%Y"), desc, f"{amount:,}", kind])

print(f"Wrote {len(rows)} transactions to {OUT}")