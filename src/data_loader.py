"""
Couche d'accès aux données : SQL -> DataFrames.

Ce module isole l'application Streamlit de la base SQLite. Si demain les données
passent dans Postgres ou Snowflake, seule cette couche change.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from . import etl

log = logging.getLogger("data_loader")


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_DB = Path("data/retail.db")
DEFAULT_CSV = Path("data/online_retail.csv")


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def ensure_database(
    csv_path: str | Path = DEFAULT_CSV,
    db_path: str | Path = DEFAULT_DB,
) -> Path:
    """Crée la base SQLite à partir du CSV si elle n'existe pas encore."""
    csv_path = Path(csv_path)
    db_path = Path(db_path)
    if db_path.exists():
        return db_path
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Données introuvables : {csv_path}. Lance `python scripts/generate_sample_data.py` "
            "ou place le fichier UCI Online Retail à cet emplacement."
        )
    log.info("Base SQLite absente — exécution du pipeline ETL")
    etl.run_pipeline(str(csv_path), str(db_path))
    return db_path


# ---------------------------------------------------------------------------
# Requêtes
# ---------------------------------------------------------------------------

_BASE_QUERY = """
    SELECT InvoiceNo, StockCode, Description, Quantity, InvoiceDate,
           UnitPrice, CustomerID, Country, IsCancellation, HasCustomer,
           Revenue, YearMonth, Year, Month, Date
    FROM transactions
"""


def load_transactions(
    db_path: str | Path = DEFAULT_DB,
    countries: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """
    Charge les transactions, avec filtres SQL optionnels.

    countries  : liste de pays à inclure (None = tous)
    start_date : 'YYYY-MM-DD' inclus
    end_date   : 'YYYY-MM-DD' inclus
    """
    db_path = Path(db_path)
    clauses, params = [], []

    if countries:
        placeholders = ",".join(["?"] * len(countries))
        clauses.append(f"Country IN ({placeholders})")
        params.extend(countries)

    if start_date:
        clauses.append("Date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("Date <= ?")
        params.append(end_date)

    query = _BASE_QUERY
    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params, parse_dates=["InvoiceDate"])

    # cast des flags
    df["IsCancellation"] = df["IsCancellation"].astype(bool)
    df["HasCustomer"] = df["HasCustomer"].astype(bool)
    return df


def list_countries(db_path: str | Path = DEFAULT_DB) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT Country FROM transactions ORDER BY Country"
        ).fetchall()
    return [r[0] for r in rows]


def date_bounds(db_path: str | Path = DEFAULT_DB) -> tuple[str, str]:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT MIN(Date), MAX(Date) FROM transactions"
        ).fetchone()
    return row[0], row[1]
