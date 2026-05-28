"""
ETL pipeline : ingestion + cleaning + chargement vers SQLite.

Étapes :
1. Lecture du CSV brut UCI Online Retail
2. Nettoyage (annulations, anomalies, valeurs manquantes)
3. Création des indicateurs métiers (Revenue, IsCancellation, YearMonth)
4. Chargement dans une base SQLite relationnelle (tables transactions + customers)

Lance ce module en CLI :
    python -m src.etl --csv data/online_retail.csv --db data/retail.db
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("etl")


# ---------------------------------------------------------------------------
# 1. Ingestion
# ---------------------------------------------------------------------------

def load_raw(csv_path: str | Path) -> pd.DataFrame:
    """Charge le CSV brut en gardant tous les enregistrements pour audit."""
    log.info("Chargement du CSV %s", csv_path)
    df = pd.read_csv(
        csv_path,
        encoding="utf-8",
        dtype={"InvoiceNo": str, "StockCode": str, "Description": str, "Country": str},
        parse_dates=["InvoiceDate"],
    )
    log.info("Lignes brutes : %s", f"{len(df):,}")
    return df


# ---------------------------------------------------------------------------
# 2. Nettoyage
# ---------------------------------------------------------------------------

def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Nettoyage automatisé :

    - flag des annulations (InvoiceNo commençant par 'C', quantités négatives)
    - suppression des lignes à prix unitaire <= 0
    - suppression des outliers de quantité (> p99.5 sur transactions positives)
    - suppression des CustomerID manquants pour les analyses client
      (gardés dans un flag has_customer pour l'analyse ventes globales)
    """
    audit = {"raw_rows": len(df)}

    # standardisation
    df = df.copy()
    df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
    df["StockCode"] = df["StockCode"].astype(str).str.strip().str.upper()
    df["Description"] = df["Description"].fillna("UNKNOWN").str.strip()
    df["Country"] = df["Country"].fillna("Unspecified").str.strip()

    # flag annulations
    df["IsCancellation"] = df["InvoiceNo"].str.startswith("C")
    audit["cancellations"] = int(df["IsCancellation"].sum())

    # prix invalides
    bad_price_mask = df["UnitPrice"] <= 0
    audit["zero_or_neg_price_dropped"] = int(bad_price_mask.sum())
    df = df.loc[~bad_price_mask].copy()

    # outliers de quantité (> p99.5 des transactions positives)
    positive = df.loc[df["Quantity"] > 0, "Quantity"]
    if len(positive) > 0:
        q_top = positive.quantile(0.995)
        outlier_mask = df["Quantity"].abs() > q_top
        audit["quantity_outliers_dropped"] = int(outlier_mask.sum())
        audit["quantity_outlier_threshold"] = float(q_top)
        df = df.loc[~outlier_mask].copy()

    # flag client identifié
    df["HasCustomer"] = df["CustomerID"].notna()
    audit["missing_customer_id"] = int((~df["HasCustomer"]).sum())

    # indicateurs métier
    df["Revenue"] = df["Quantity"] * df["UnitPrice"]
    df["YearMonth"] = df["InvoiceDate"].dt.to_period("M").astype(str)
    df["Year"] = df["InvoiceDate"].dt.year
    df["Month"] = df["InvoiceDate"].dt.month
    df["Date"] = df["InvoiceDate"].dt.date.astype(str)

    # CustomerID en string nullable (évite les .0 et les NaN dans SQLite)
    df["CustomerID"] = df["CustomerID"].astype("Int64").astype(str).replace("<NA>", None)

    audit["clean_rows"] = len(df)
    audit["clean_revenue_total"] = float(df.loc[~df["IsCancellation"], "Revenue"].sum())
    audit["net_revenue_total"] = float(df["Revenue"].sum())

    log.info("Lignes nettoyées : %s", f"{len(df):,}")
    log.info("Annulations détectées : %s", f"{audit['cancellations']:,}")
    log.info(
        "Outliers quantité supprimés : %s (seuil = %s)",
        f"{audit.get('quantity_outliers_dropped', 0):,}",
        f"{audit.get('quantity_outlier_threshold', 0):.0f}",
    )

    return df, audit


# ---------------------------------------------------------------------------
# 3. Chargement SQLite
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
DROP TABLE IF EXISTS transactions;
CREATE TABLE transactions (
    InvoiceNo       TEXT,
    StockCode       TEXT,
    Description     TEXT,
    Quantity        INTEGER,
    InvoiceDate     TEXT,
    UnitPrice       REAL,
    CustomerID      TEXT,
    Country         TEXT,
    IsCancellation  INTEGER,
    HasCustomer     INTEGER,
    Revenue         REAL,
    YearMonth       TEXT,
    Year            INTEGER,
    Month           INTEGER,
    Date            TEXT
);
CREATE INDEX idx_tx_customer  ON transactions(CustomerID);
CREATE INDEX idx_tx_date      ON transactions(InvoiceDate);
CREATE INDEX idx_tx_country   ON transactions(Country);
CREATE INDEX idx_tx_yearmonth ON transactions(YearMonth);

DROP TABLE IF EXISTS customers;
CREATE TABLE customers (
    CustomerID  TEXT PRIMARY KEY,
    Country     TEXT,
    FirstOrder  TEXT,
    LastOrder   TEXT,
    NumOrders   INTEGER,
    NetRevenue  REAL
);
"""


def write_sqlite(df: pd.DataFrame, db_path: str | Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    log.info("Création de la base SQLite %s", db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)

        # transactions
        df_sql = df.copy()
        df_sql["InvoiceDate"] = df_sql["InvoiceDate"].astype(str)
        df_sql["IsCancellation"] = df_sql["IsCancellation"].astype(int)
        df_sql["HasCustomer"] = df_sql["HasCustomer"].astype(int)
        df_sql.to_sql("transactions", conn, if_exists="append", index=False, chunksize=5000)

        # table customers (agrégat de référence — facilite les jointures front)
        cust = (
            df_sql.loc[(df_sql["HasCustomer"] == 1) & (df_sql["IsCancellation"] == 0)]
            .groupby("CustomerID")
            .agg(
                Country=("Country", "last"),
                FirstOrder=("InvoiceDate", "min"),
                LastOrder=("InvoiceDate", "max"),
                NumOrders=("InvoiceNo", "nunique"),
                NetRevenue=("Revenue", "sum"),
            )
            .reset_index()
        )
        cust.to_sql("customers", conn, if_exists="append", index=False)

    log.info("Chargées : %s transactions, %s clients agrégés", f"{len(df_sql):,}", f"{len(cust):,}")


# ---------------------------------------------------------------------------
# 4. CLI
# ---------------------------------------------------------------------------

def run_pipeline(csv_path: str, db_path: str) -> dict:
    df = load_raw(csv_path)
    df_clean, audit = clean(df)
    write_sqlite(df_clean, db_path)
    return audit


def main():
    parser = argparse.ArgumentParser(description="ETL Online Retail -> SQLite")
    parser.add_argument("--csv", default="data/online_retail.csv")
    parser.add_argument("--db", default="data/retail.db")
    args = parser.parse_args()

    audit = run_pipeline(args.csv, args.db)
    print("\n=== Rapport de pipeline ===")
    for k, v in audit.items():
        if isinstance(v, float):
            print(f"  {k:30s} : {v:,.2f}")
        else:
            print(f"  {k:30s} : {v:,}" if isinstance(v, int) else f"  {k:30s} : {v}")


if __name__ == "__main__":
    main()
