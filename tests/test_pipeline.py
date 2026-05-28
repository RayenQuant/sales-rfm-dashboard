"""Tests unitaires : ETL, KPI, RFM, simulation."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import etl, kpis, rfm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_df():
    """Mini dataset brut couvrant : transactions normales, annulation, anomalie."""
    return pd.DataFrame([
        # invoice, stock, desc, qty, date, price, customer, country
        ("100001", "A1", "Item A", 5,   "2025-01-05 10:00:00", 2.50, 12345, "United Kingdom"),
        ("100001", "B1", "Item B", 2,   "2025-01-05 10:00:00", 5.00, 12345, "United Kingdom"),
        ("100002", "A1", "Item A", 3,   "2025-02-10 14:00:00", 2.50, 12346, "France"),
        ("C00003", "A1", "Item A", -1,  "2025-02-15 09:00:00", 2.50, 12345, "United Kingdom"),  # annulation
        ("100004", "C1", "Item C", 1,   "2025-03-01 12:00:00", 0.0,  12347, "Germany"),         # prix=0
        ("100005", "A1", "Item A", 2,   "2025-04-01 12:00:00", 2.50, None,  "United Kingdom"),  # CustomerID manquant
        ("100006", "A1", "Item A", 99999,"2025-05-01 12:00:00", 2.50, 12348, "Spain"),          # outlier
        # bourrer pour avoir un p99.5 stable
        *[("100100", "A1", "Item A", 5, "2025-06-01 10:00:00", 2.50, 12349 + i, "United Kingdom")
          for i in range(50)],
    ], columns=["InvoiceNo", "StockCode", "Description", "Quantity",
                "InvoiceDate", "UnitPrice", "CustomerID", "Country"])


@pytest.fixture
def clean_df(raw_df):
    raw_df["InvoiceDate"] = pd.to_datetime(raw_df["InvoiceDate"])
    df, _ = etl.clean(raw_df)
    return df


# ---------------------------------------------------------------------------
# ETL
# ---------------------------------------------------------------------------

class TestETL:

    def test_clean_removes_zero_price(self, raw_df):
        raw_df["InvoiceDate"] = pd.to_datetime(raw_df["InvoiceDate"])
        df, audit = etl.clean(raw_df)
        assert (df["UnitPrice"] > 0).all()
        assert audit["zero_or_neg_price_dropped"] == 1

    def test_clean_flags_cancellations(self, clean_df):
        cancel = clean_df.loc[clean_df["IsCancellation"]]
        assert len(cancel) == 1
        assert cancel.iloc[0]["InvoiceNo"].startswith("C")
        assert cancel.iloc[0]["Revenue"] < 0  # CA négatif pour annulations

    def test_clean_removes_outliers(self, raw_df):
        raw_df["InvoiceDate"] = pd.to_datetime(raw_df["InvoiceDate"])
        df, audit = etl.clean(raw_df)
        assert audit["quantity_outliers_dropped"] >= 1
        # le 99999 a été supprimé
        assert (df["Quantity"].abs() < 99999).all()

    def test_clean_keeps_missing_customer_for_global_kpis(self, clean_df):
        # ligne avec CustomerID manquant doit toujours être présente
        assert (~clean_df["HasCustomer"]).sum() == 1

    def test_clean_computes_revenue(self, clean_df):
        # Vérifie qu'on a bien Revenue = Quantity * UnitPrice partout
        recomputed = clean_df["Quantity"] * clean_df["UnitPrice"]
        assert np.allclose(clean_df["Revenue"], recomputed)

    def test_etl_writes_sqlite(self, raw_df, tmp_path):
        csv_path = tmp_path / "raw.csv"
        db_path = tmp_path / "test.db"
        raw_df.to_csv(csv_path, index=False)
        audit = etl.run_pipeline(str(csv_path), str(db_path))
        assert db_path.exists()
        assert audit["clean_rows"] > 0


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

class TestKPIs:

    def test_headline_kpis_returns_expected_keys(self, clean_df):
        k = kpis.headline_kpis(clean_df)
        assert {"net_revenue", "gross_revenue", "cancellation_rate",
                "n_orders", "n_customers", "aov", "units_sold"} <= k.keys()

    def test_net_revenue_excludes_cancellation_value(self, clean_df):
        k = kpis.headline_kpis(clean_df)
        # net = gross - cancel_value
        assert k["net_revenue"] <= k["gross_revenue"]
        assert k["cancellation_rate"] >= 0

    def test_aov_is_per_invoice(self, clean_df):
        k = kpis.headline_kpis(clean_df)
        valid = clean_df.loc[~clean_df["IsCancellation"]]
        expected = valid.groupby("InvoiceNo")["Revenue"].sum().mean()
        assert k["aov"] == pytest.approx(expected)

    def test_monthly_revenue_has_mom(self, clean_df):
        m = kpis.monthly_revenue(clean_df)
        assert "MoM" in m.columns
        # première période n'a pas de MoM
        assert pd.isna(m["MoM"].iloc[0])

    def test_top_products_excludes_cancellations(self, clean_df):
        tp = kpis.top_products(clean_df, 5)
        assert (tp["Revenue"] > 0).all()

    def test_empty_dataframe(self):
        empty = pd.DataFrame(columns=["InvoiceNo", "IsCancellation", "Revenue",
                                       "CustomerID", "Quantity", "HasCustomer",
                                       "YearMonth", "Date", "StockCode", "Description",
                                       "Country"])
        k = kpis.headline_kpis(empty)
        assert k["net_revenue"] == 0
        assert k["n_orders"] == 0


# ---------------------------------------------------------------------------
# Simulation tarifaire
# ---------------------------------------------------------------------------

class TestPriceSimulation:

    def test_zero_change_returns_baseline(self, clean_df):
        sim = kpis.simulate_price_change(clean_df, 0.0)
        assert sim["delta_revenue"] == pytest.approx(0.0, abs=1)
        assert sim["delta_margin"] == pytest.approx(0.0, abs=1)

    def test_price_increase_improves_margin(self, clean_df):
        """+5% prix : malgré la baisse de volumes (élasticité), la marge grimpe
        car le COGS suit la quantité, pas le prix."""
        sim = kpis.simulate_price_change(clean_df, 0.05, cogs_ratio=0.55)
        assert sim["delta_margin"] > 0

    def test_extreme_increase_kills_demand(self, clean_df):
        """À +100%, l'élasticité -1.2 fait passer le qty_factor sous 0 → clipped à 0."""
        sim = kpis.simulate_price_change(clean_df, 1.0)
        assert sim["qty_factor"] >= 0
        assert sim["new_revenue"] >= 0


# ---------------------------------------------------------------------------
# RFM
# ---------------------------------------------------------------------------

class TestRFM:

    def test_compute_rfm_excludes_cancellations_and_missing_ids(self, clean_df):
        rfm_df = rfm.compute_rfm(clean_df)
        # Les annulations et CustomerID manquants n'apparaissent pas
        valid_ids = clean_df.loc[
            (~clean_df["IsCancellation"]) & (clean_df["HasCustomer"]),
            "CustomerID"
        ].dropna().unique()
        assert set(rfm_df["CustomerID"]) == set(valid_ids)

    def test_compute_rfm_has_positive_monetary(self, clean_df):
        rfm_df = rfm.compute_rfm(clean_df)
        assert (rfm_df["Monetary"] > 0).all()
        assert (rfm_df["Recency"] >= 0).all()
        assert (rfm_df["Frequency"] >= 1).all()

    def test_score_rfm_produces_segments(self, clean_df):
        rfm_df = rfm.compute_rfm(clean_df)
        scored = rfm.score_rfm(rfm_df)
        assert "Segment" in scored.columns
        assert scored["Segment"].notna().all()
        # Tous les segments sont dans la liste canonique
        assert scored["Segment"].isin(rfm.SEGMENT_ORDER).all()

    def test_scores_are_in_range_1_5(self, clean_df):
        rfm_df = rfm.compute_rfm(clean_df)
        scored = rfm.score_rfm(rfm_df)
        for col in ["R", "F", "M"]:
            assert scored[col].between(1, 5).all()

    def test_segment_summary_sums_to_total(self, clean_df):
        rfm_df = rfm.compute_rfm(clean_df)
        scored = rfm.score_rfm(rfm_df)
        summary = rfm.segment_summary(scored)
        assert summary["Customers"].sum() == len(scored)
        assert summary["Share"].sum() == pytest.approx(1.0)
        # Recommandations toutes présentes
        assert summary["Recommendation"].notna().all()
