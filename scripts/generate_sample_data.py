"""
Generate a realistic sample dataset that mimics the UCI Online Retail Dataset structure.

This script creates ~50,000 transactions across ~12 months with realistic patterns:
- Customer IDs with varying activity levels (Pareto distribution)
- Multiple countries (UK-dominant, as in the real dataset)
- Seasonality (Q4 peak for retail)
- Cancellations (invoices starting with 'C', negative quantities)
- Anomalies (some zero/negative prices, missing customer IDs)

In production, replace this with the actual UCI dataset:
    https://archive.ics.uci.edu/ml/datasets/online+retail
    or https://www.kaggle.com/datasets/carrie1/ecommerce-data

Usage:
    python scripts/generate_sample_data.py
"""

from __future__ import annotations

import argparse
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
random.seed(42)


# ---------------------------------------------------------------------------
# Reference catalogues
# ---------------------------------------------------------------------------

PRODUCTS = [
    ("85123A", "WHITE HANGING HEART T-LIGHT HOLDER", 2.55),
    ("71053",  "WHITE METAL LANTERN", 3.39),
    ("84406B", "CREAM CUPID HEARTS COAT HANGER", 2.75),
    ("84029G", "KNITTED UNION FLAG HOT WATER BOTTLE", 3.39),
    ("84029E", "RED WOOLLY HOTTIE WHITE HEART", 3.39),
    ("22752",  "SET 7 BABUSHKA NESTING BOXES", 7.65),
    ("21730",  "GLASS STAR FROSTED T-LIGHT HOLDER", 4.25),
    ("22633",  "HAND WARMER UNION JACK", 1.85),
    ("22632",  "HAND WARMER RED POLKA DOT", 1.85),
    ("84879",  "ASSORTED COLOUR BIRD ORNAMENT", 1.69),
    ("22745",  "POPPY'S PLAYHOUSE BEDROOM", 2.10),
    ("22748",  "POPPY'S PLAYHOUSE KITCHEN", 2.10),
    ("22310",  "IVORY KNITTED MUG COSY", 1.65),
    ("84969",  "BOX OF 6 ASSORTED COLOUR TEASPOONS", 4.25),
    ("22623",  "BOX OF VINTAGE JIGSAW BLOCKS", 4.95),
    ("22622",  "BOX OF VINTAGE ALPHABET BLOCKS", 9.95),
    ("21754",  "HOME BUILDING BLOCK WORD", 5.95),
    ("21755",  "LOVE BUILDING BLOCK WORD", 5.95),
    ("21777",  "RECIPE BOX WITH METAL HEART", 7.95),
    ("48187",  "DOORMAT NEW ENGLAND", 7.95),
    ("22720",  "SET OF 3 CAKE TINS PANTRY DESIGN", 4.95),
    ("47566",  "PARTY BUNTING", 4.95),
    ("23084",  "RABBIT NIGHT LIGHT", 2.08),
    ("21232",  "STRAWBERRY CERAMIC TRINKET POT", 1.25),
    ("22197",  "POPCORN HOLDER", 0.85),
    ("85099B", "JUMBO BAG RED RETROSPOT", 2.08),
    ("20725",  "LUNCH BAG RED RETROSPOT", 1.65),
    ("22383",  "LUNCH BAG SUKI DESIGN", 1.65),
    ("22384",  "LUNCH BAG PINK POLKADOT", 1.65),
    ("20727",  "LUNCH BAG BLACK SKULL", 1.65),
    ("22386",  "JUMBO BAG PINK POLKADOT", 2.08),
    ("85099C", "JUMBO BAG BAROQUE BLACK WHITE", 2.08),
    ("23202",  "JUMBO BAG VINTAGE LEAF", 2.08),
    ("22411",  "JUMBO SHOPPER VINTAGE RED PAISLEY", 2.08),
    ("22382",  "LUNCH BAG SPACEBOY DESIGN", 1.65),
    ("23203",  "JUMBO BAG DOILEY PATTERNS", 2.08),
    ("22662",  "LUNCH BAG DOLLY GIRL DESIGN", 1.65),
    ("23206",  "LUNCH BAG APPLE DESIGN", 1.65),
    ("23207",  "LUNCH BAG ALPHABET DESIGN", 1.65),
    ("22139",  "RETROSPOT TEA SET CERAMIC 11 PC", 4.95),
    ("22699",  "ROSES REGENCY TEACUP AND SAUCER", 2.95),
    ("22697",  "GREEN REGENCY TEACUP AND SAUCER", 2.95),
    ("22698",  "PINK REGENCY TEACUP AND SAUCER", 2.95),
    ("23298",  "SPOTTY BUNTING", 4.95),
    ("21212",  "PACK OF 72 RETROSPOT CAKE CASES", 0.55),
    ("22086",  "PAPER CHAIN KIT 50'S CHRISTMAS", 2.95),
    ("22910",  "PAPER CHAIN KIT VINTAGE CHRISTMAS", 2.95),
    ("85123a", "WHITE HANGING HEART T-LIGHT HOLDER", 2.95),
    ("23355",  "HOT WATER BOTTLE KEEP CALM", 4.95),
    ("23356",  "LOVE HOT WATER BOTTLE", 5.95),
]

COUNTRY_WEIGHTS = {
    "United Kingdom": 0.89,
    "Germany":        0.022,
    "France":         0.020,
    "EIRE":           0.015,
    "Spain":          0.008,
    "Netherlands":    0.007,
    "Belgium":        0.006,
    "Switzerland":    0.005,
    "Portugal":       0.004,
    "Australia":      0.004,
    "Norway":         0.003,
    "Italy":          0.003,
    "Channel Islands":0.003,
    "Finland":        0.002,
    "Cyprus":         0.002,
    "Sweden":         0.002,
    "Austria":        0.002,
    "Denmark":        0.002,
}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_transactions(n_target: int, start: datetime, end: datetime) -> pd.DataFrame:
    """Generate ~n_target rows of synthetic retail transactions."""
    # Pareto-ish customer base: 5,000 customers, a few power buyers
    n_customers = 5000
    customer_ids = np.arange(12346, 12346 + n_customers)
    # power-law activity weights
    activity = RNG.pareto(a=1.5, size=n_customers) + 1.0
    activity = activity / activity.sum()

    countries = list(COUNTRY_WEIGHTS.keys())
    country_p = np.array(list(COUNTRY_WEIGHTS.values()))
    country_p = country_p / country_p.sum()
    cust_country = RNG.choice(countries, size=n_customers, p=country_p)

    # number of invoices per customer (roughly proportional to activity)
    invoices_per_customer = np.maximum(1, RNG.poisson(activity * n_target / 18, size=n_customers))
    total_invoices = int(invoices_per_customer.sum())

    rows = []
    invoice_counter = 536365  # like the real dataset

    total_days = (end - start).days

    for cust_idx, n_inv in enumerate(invoices_per_customer):
        cid = int(customer_ids[cust_idx])
        country = cust_country[cust_idx]
        for _ in range(n_inv):
            # date with Q4 seasonality bump
            day_offset = int(RNG.integers(0, total_days))
            invoice_dt = start + timedelta(days=day_offset,
                                            hours=int(RNG.integers(8, 19)),
                                            minutes=int(RNG.integers(0, 60)))
            # boost Q4
            if invoice_dt.month in (10, 11, 12):
                if RNG.random() < 0.35:
                    day_offset = int(RNG.integers(int(total_days * 0.7), total_days))
                    invoice_dt = start + timedelta(days=day_offset,
                                                    hours=int(RNG.integers(8, 19)),
                                                    minutes=int(RNG.integers(0, 60)))

            invoice_no = str(invoice_counter)
            invoice_counter += 1

            # 1-12 lines per invoice
            n_lines = int(RNG.integers(1, 13))
            picked = RNG.choice(len(PRODUCTS), size=n_lines, replace=False)
            for p in picked:
                code, desc, unit_price = PRODUCTS[p]
                qty = int(max(1, RNG.poisson(6)))
                # price noise +/- 10%
                price = round(unit_price * float(RNG.uniform(0.9, 1.1)), 2)
                rows.append((invoice_no, code, desc, qty, invoice_dt, price, cid, country))

            if len(rows) >= n_target:
                break
        if len(rows) >= n_target:
            break

    df = pd.DataFrame(rows, columns=[
        "InvoiceNo", "StockCode", "Description", "Quantity",
        "InvoiceDate", "UnitPrice", "CustomerID", "Country",
    ])

    # ---- inject realistic noise ---------------------------------------------
    n = len(df)

    # 1.5% missing CustomerID
    miss_idx = RNG.choice(n, size=int(n * 0.015), replace=False)
    df.loc[miss_idx, "CustomerID"] = np.nan

    # ~2% cancellations: invoice prefixed with 'C', negative quantity
    cancel_idx = RNG.choice(n, size=int(n * 0.02), replace=False)
    df.loc[cancel_idx, "InvoiceNo"] = "C" + df.loc[cancel_idx, "InvoiceNo"].astype(str)
    df.loc[cancel_idx, "Quantity"] = -df.loc[cancel_idx, "Quantity"].abs()

    # 0.3% zero or negative unit prices (anomalies)
    bad_price_idx = RNG.choice(n, size=int(n * 0.003), replace=False)
    df.loc[bad_price_idx, "UnitPrice"] = 0.0

    # 0.2% extreme outlier quantities
    outlier_idx = RNG.choice(n, size=int(n * 0.002), replace=False)
    df.loc[outlier_idx, "Quantity"] = int(RNG.integers(1000, 80000))

    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=50000,
                        help="Approximate number of transaction rows to generate")
    parser.add_argument("--out", type=str, default="data/online_retail.csv")
    args = parser.parse_args()

    start = datetime(2024, 12, 1)
    end = datetime(2025, 12, 9)

    print(f"Generating ~{args.rows:,} synthetic transactions from {start.date()} to {end.date()} ...")
    df = generate_transactions(args.rows, start, end)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    print(f"Wrote {len(df):,} rows to {out_path}")
    print(f"  Unique customers : {df['CustomerID'].nunique():,}")
    print(f"  Unique invoices  : {df['InvoiceNo'].nunique():,}")
    print(f"  Countries        : {df['Country'].nunique()}")
    print(f"  Cancellations    : {df['InvoiceNo'].astype(str).str.startswith('C').sum():,}")
    print(f"  Missing CustID   : {df['CustomerID'].isna().sum():,}")


if __name__ == "__main__":
    main()
