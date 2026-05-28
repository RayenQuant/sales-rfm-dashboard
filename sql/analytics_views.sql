-- =============================================================================
-- Vues SQL analytiques sur la base retail.db
-- =============================================================================
-- Ce fichier illustre les requêtes SQL qui sous-tendent les KPI exécutifs.
-- Il peut être exécuté contre la base SQLite créée par `src/etl.py` :
--
--     sqlite3 data/retail.db < sql/analytics_views.sql
--
-- Toutes les vues excluent les annulations (IsCancellation = 1) sauf mention
-- explicite, afin de refléter le chiffre d'affaires effectivement réalisé.
-- =============================================================================


-- 1. Vue mensuelle : CA net, commandes, panier moyen, croissance MoM
DROP VIEW IF EXISTS v_monthly_kpis;
CREATE VIEW v_monthly_kpis AS
WITH monthly AS (
    SELECT
        YearMonth,
        ROUND(SUM(Revenue), 2)                                AS net_revenue,
        COUNT(DISTINCT InvoiceNo)                             AS n_orders,
        ROUND(SUM(Revenue) * 1.0 / COUNT(DISTINCT InvoiceNo), 2) AS aov,
        COUNT(DISTINCT CustomerID)                            AS n_customers
    FROM transactions
    WHERE IsCancellation = 0
    GROUP BY YearMonth
)
SELECT
    m.YearMonth,
    m.net_revenue,
    m.n_orders,
    m.aov,
    m.n_customers,
    ROUND(
        (m.net_revenue - LAG(m.net_revenue) OVER (ORDER BY m.YearMonth))
        * 1.0 / NULLIF(LAG(m.net_revenue) OVER (ORDER BY m.YearMonth), 0),
        4
    ) AS mom_growth
FROM monthly m
ORDER BY m.YearMonth;


-- 2. Top produits par chiffre d'affaires
DROP VIEW IF EXISTS v_top_products;
CREATE VIEW v_top_products AS
SELECT
    StockCode,
    Description,
    ROUND(SUM(Revenue), 2) AS revenue,
    SUM(Quantity)          AS units_sold,
    COUNT(DISTINCT InvoiceNo) AS orders
FROM transactions
WHERE IsCancellation = 0
GROUP BY StockCode, Description
ORDER BY revenue DESC;


-- 3. Performance par pays
DROP VIEW IF EXISTS v_country_performance;
CREATE VIEW v_country_performance AS
SELECT
    Country,
    ROUND(SUM(Revenue), 2)        AS revenue,
    COUNT(DISTINCT InvoiceNo)     AS orders,
    COUNT(DISTINCT CustomerID)    AS customers,
    ROUND(AVG(Revenue), 2)        AS avg_line_revenue
FROM transactions
WHERE IsCancellation = 0
GROUP BY Country
ORDER BY revenue DESC;


-- 4. Base d'analyse RFM (peut être consommée par Python ou un BI tool)
DROP VIEW IF EXISTS v_rfm_base;
CREATE VIEW v_rfm_base AS
WITH snapshot AS (
    SELECT MAX(DATE(InvoiceDate)) AS snap_date
    FROM transactions
    WHERE IsCancellation = 0
)
SELECT
    t.CustomerID,
    MAX(t.Country)                                       AS country,
    CAST(JULIANDAY((SELECT snap_date FROM snapshot))
         - JULIANDAY(MAX(DATE(t.InvoiceDate))) AS INTEGER) AS recency_days,
    COUNT(DISTINCT t.InvoiceNo)                          AS frequency,
    ROUND(SUM(t.Revenue), 2)                             AS monetary
FROM transactions t
WHERE t.IsCancellation = 0
  AND t.HasCustomer    = 1
GROUP BY t.CustomerID;


-- 5. Impact financier des annulations (pour audit)
DROP VIEW IF EXISTS v_cancellation_impact;
CREATE VIEW v_cancellation_impact AS
SELECT
    YearMonth,
    ROUND(SUM(CASE WHEN IsCancellation = 0 THEN Revenue ELSE 0 END), 2)       AS gross_revenue,
    ROUND(-SUM(CASE WHEN IsCancellation = 1 THEN Revenue ELSE 0 END), 2)      AS cancellation_value,
    ROUND(SUM(Revenue), 2)                                                    AS net_revenue,
    COUNT(DISTINCT CASE WHEN IsCancellation = 1 THEN InvoiceNo END)            AS n_cancellations
FROM transactions
GROUP BY YearMonth
ORDER BY YearMonth;
