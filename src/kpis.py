"""
Métriques exécutives : KPI ventes, évolution mensuelle, top produits, pays.

Toutes les fonctions reçoivent un DataFrame déjà nettoyé (cf. src.etl).
Les annulations sont incluses dans `Revenue` (en négatif) pour refléter
le chiffre d'affaires net effectivement encaissé.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

def headline_kpis(df: pd.DataFrame) -> dict:
    """Retourne les KPI exécutifs principaux."""
    if df.empty:
        return {
            "net_revenue": 0.0,
            "gross_revenue": 0.0,
            "cancellation_rate": 0.0,
            "n_orders": 0,
            "n_customers": 0,
            "aov": 0.0,
            "units_sold": 0,
        }

    gross = df.loc[~df["IsCancellation"], "Revenue"].sum()
    cancellations = -df.loc[df["IsCancellation"], "Revenue"].sum()
    net = gross - cancellations

    # Une commande = un InvoiceNo non-annulé
    valid = df.loc[~df["IsCancellation"]]
    n_orders = valid["InvoiceNo"].nunique()
    aov = float(valid.groupby("InvoiceNo")["Revenue"].sum().mean()) if n_orders else 0.0

    return {
        "net_revenue": float(net),
        "gross_revenue": float(gross),
        "cancellation_rate": float(cancellations / gross) if gross > 0 else 0.0,
        "n_orders": int(n_orders),
        "n_customers": int(valid.loc[valid["HasCustomer"] == 1, "CustomerID"].nunique()),
        "aov": aov,
        "units_sold": int(valid["Quantity"].sum()),
    }


# ---------------------------------------------------------------------------
# Évolution temporelle
# ---------------------------------------------------------------------------

def monthly_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """Chiffre d'affaires net mensuel + croissance MoM."""
    if df.empty:
        return pd.DataFrame(columns=["YearMonth", "Revenue", "MoM"])

    monthly = (
        df.groupby("YearMonth")["Revenue"].sum()
        .reset_index()
        .sort_values("YearMonth")
    )
    monthly["MoM"] = monthly["Revenue"].pct_change()
    return monthly


def daily_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """CA net quotidien (utile pour une vue zoomée)."""
    if df.empty:
        return pd.DataFrame(columns=["Date", "Revenue"])
    daily = df.groupby("Date")["Revenue"].sum().reset_index().sort_values("Date")
    daily["Date"] = pd.to_datetime(daily["Date"])
    return daily


def mom_growth(df: pd.DataFrame) -> float:
    """Croissance du dernier mois clos vs précédent."""
    m = monthly_revenue(df)
    if len(m) < 2:
        return 0.0
    return float(m["MoM"].iloc[-1]) if pd.notna(m["MoM"].iloc[-1]) else 0.0


# ---------------------------------------------------------------------------
# Top produits & pays
# ---------------------------------------------------------------------------

def top_products(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    valid = df.loc[~df["IsCancellation"]]
    if valid.empty:
        return pd.DataFrame(columns=["StockCode", "Description", "Revenue", "Units"])
    g = (
        valid.groupby(["StockCode", "Description"])
        .agg(Revenue=("Revenue", "sum"), Units=("Quantity", "sum"))
        .reset_index()
        .sort_values("Revenue", ascending=False)
        .head(n)
    )
    return g


def top_countries(df: pd.DataFrame, n: int = 10, exclude_uk: bool = False) -> pd.DataFrame:
    valid = df.loc[~df["IsCancellation"]]
    if exclude_uk:
        valid = valid.loc[valid["Country"] != "United Kingdom"]
    if valid.empty:
        return pd.DataFrame(columns=["Country", "Revenue", "Orders"])
    g = (
        valid.groupby("Country")
        .agg(Revenue=("Revenue", "sum"), Orders=("InvoiceNo", "nunique"))
        .reset_index()
        .sort_values("Revenue", ascending=False)
        .head(n)
    )
    return g


# ---------------------------------------------------------------------------
# Simulation tarifaire
# ---------------------------------------------------------------------------

def simulate_price_change(df: pd.DataFrame, pct: float, cogs_ratio: float = 0.55) -> dict:
    """
    Simule l'impact d'une variation tarifaire `pct` (ex : +0.05 pour +5%)
    en supposant un coût des marchandises vendues = `cogs_ratio` × prix actuel,
    et une élasticité prix-demande modérée (-1.2).

    Renvoie un dict comparant scénario actuel vs scénario simulé.
    """
    valid = df.loc[~df["IsCancellation"]].copy()
    if valid.empty:
        return {"current_revenue": 0.0, "new_revenue": 0.0, "current_margin": 0.0,
                "new_margin": 0.0, "delta_revenue": 0.0, "delta_margin": 0.0}

    elasticity = -1.2  # baisse de demande lorsque le prix monte
    qty_factor = 1.0 + elasticity * pct
    qty_factor = max(qty_factor, 0.0)

    current_rev = float(valid["Revenue"].sum())
    current_cogs = current_rev * cogs_ratio
    current_margin = current_rev - current_cogs

    new_rev = float((valid["Revenue"] * (1 + pct) * qty_factor).sum())
    # le coût unitaire est constant => le COGS bouge proportionnellement à la quantité
    new_cogs = current_cogs * qty_factor
    new_margin = new_rev - new_cogs

    return {
        "current_revenue": current_rev,
        "new_revenue": new_rev,
        "current_margin": current_margin,
        "new_margin": new_margin,
        "delta_revenue": new_rev - current_rev,
        "delta_margin": new_margin - current_margin,
        "qty_factor": qty_factor,
    }
