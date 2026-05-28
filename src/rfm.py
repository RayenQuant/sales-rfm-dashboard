"""
Segmentation RFM : Récence, Fréquence, Montant.

Approche :
1. Calcul des trois métriques par client (sur transactions hors annulations
   et avec CustomerID connu)
2. Score 1-5 sur chaque dimension via quintiles (qcut), avec gestion robuste
   des ex-aequos (rang relatif)
3. Mapping vers segments métier interprétables

Segments métiers :
    Champions             — meilleurs clients, achètent souvent et récemment
    Loyal Customers       — clients fidèles à fort potentiel
    Potential Loyalists   — clients récents avec une bonne fréquence
    New Customers         — premiers achats récents
    Promising             — récents mais peu de répétition
    Need Attention        — moyens partout, attention à la dérive
    About to Sleep        — baisse de récence
    At Risk               — bons clients qui ne reviennent plus
    Cannot Lose Them      — anciens VIP, à reconquérir d'urgence
    Hibernating           — long sommeil, faible valeur
    Lost                  — perdus
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# 1. Métriques RFM
# ---------------------------------------------------------------------------

def compute_rfm(df: pd.DataFrame, snapshot_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Calcule R, F, M par CustomerID."""
    valid = df.loc[(~df["IsCancellation"]) & (df["HasCustomer"] == 1)].copy()
    if valid.empty:
        return pd.DataFrame(columns=["CustomerID", "Recency", "Frequency", "Monetary"])

    valid["InvoiceDate"] = pd.to_datetime(valid["InvoiceDate"])
    if snapshot_date is None:
        snapshot_date = valid["InvoiceDate"].max() + pd.Timedelta(days=1)

    rfm = (
        valid.groupby("CustomerID")
        .agg(
            Recency=("InvoiceDate", lambda s: (snapshot_date - s.max()).days),
            Frequency=("InvoiceNo", "nunique"),
            Monetary=("Revenue", "sum"),
        )
        .reset_index()
    )
    return rfm


# ---------------------------------------------------------------------------
# 2. Scoring 1-5
# ---------------------------------------------------------------------------

def _safe_qcut(s: pd.Series, ascending: bool) -> pd.Series:
    """
    Découpe en quintiles avec gestion des ex-aequos (rank-based) et fallback
    si la série a peu de valeurs uniques. Renvoie un score 1..5 (int).
    Pour la Recency, ascending=False : score 5 = recency la plus FAIBLE (bon).
    Pour F et M, ascending=True : score 5 = valeur la plus ÉLEVÉE (bon).
    """
    if s.nunique() < 5:
        # cas dégénéré : fall back sur une normalisation simple
        ranks = s.rank(method="average", ascending=ascending)
        scaled = (ranks - ranks.min()) / max(ranks.max() - ranks.min(), 1)
        return (1 + (scaled * 4)).round().astype(int).clip(1, 5)

    ranked = s.rank(method="first", ascending=ascending)
    return pd.qcut(ranked, 5, labels=[1, 2, 3, 4, 5]).astype(int)


def score_rfm(rfm: pd.DataFrame) -> pd.DataFrame:
    if rfm.empty:
        rfm[["R", "F", "M", "RFM_Score", "Segment"]] = None
        return rfm

    out = rfm.copy()
    out["R"] = _safe_qcut(out["Recency"], ascending=False)
    out["F"] = _safe_qcut(out["Frequency"], ascending=True)
    out["M"] = _safe_qcut(out["Monetary"], ascending=True)
    out["RFM_Score"] = out["R"].astype(str) + out["F"].astype(str) + out["M"].astype(str)
    out["Segment"] = out.apply(_assign_segment, axis=1)
    return out


# ---------------------------------------------------------------------------
# 3. Mapping segments métier
# ---------------------------------------------------------------------------

def _assign_segment(row) -> str:
    r, f, m = row["R"], row["F"], row["M"]

    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 4:
        return "Loyal Customers"
    if r >= 4 and f <= 2:
        if f == 1:
            return "New Customers"
        return "Potential Loyalists"
    if r >= 4 and m >= 3:
        return "Potential Loyalists"
    if r == 3 and f <= 2:
        return "Promising"
    if r == 3 and f >= 3:
        return "Need Attention"
    if r == 2 and f >= 3 and m >= 3:
        return "At Risk"
    if r <= 2 and f >= 4 and m >= 4:
        return "Cannot Lose Them"
    if r == 2 and f <= 2:
        return "About to Sleep"
    if r == 1 and f <= 2:
        return "Lost"
    return "Hibernating"


SEGMENT_ORDER = [
    "Champions",
    "Loyal Customers",
    "Potential Loyalists",
    "New Customers",
    "Promising",
    "Need Attention",
    "About to Sleep",
    "At Risk",
    "Cannot Lose Them",
    "Hibernating",
    "Lost",
]


SEGMENT_RECOMMENDATIONS = {
    "Champions":          "Programme VIP, ambassadeurs, accès avant-première.",
    "Loyal Customers":    "Upsell ciblé, parrainage, fidélisation premium.",
    "Potential Loyalists":"Onboarding poussé, offre 2e commande, cross-sell.",
    "New Customers":      "Email de bienvenue, garantie satisfait, kit découverte.",
    "Promising":          "Relance post-1ère commande, incitation à fréquence.",
    "Need Attention":     "Reactivation soft, recommandations personnalisées.",
    "About to Sleep":     "Offre déclic limitée dans le temps, repositionner.",
    "At Risk":            "Reconquête prioritaire, contact direct, geste commercial.",
    "Cannot Lose Them":   "Win-back haute priorité, account manager dédié.",
    "Hibernating":        "Campagne de réveil low-cost, segmentation profonde.",
    "Lost":               "Désengager si non rentable, garder en list froide.",
}


def segment_summary(scored_rfm: pd.DataFrame) -> pd.DataFrame:
    """Agrège les segments : nb clients, % base, monétaire moyen, total."""
    if scored_rfm.empty:
        return pd.DataFrame(columns=["Segment", "Customers", "Share", "AvgMonetary", "TotalMonetary"])

    total = len(scored_rfm)
    g = (
        scored_rfm.groupby("Segment")
        .agg(
            Customers=("CustomerID", "count"),
            AvgMonetary=("Monetary", "mean"),
            TotalMonetary=("Monetary", "sum"),
            AvgRecency=("Recency", "mean"),
            AvgFrequency=("Frequency", "mean"),
        )
        .reset_index()
    )
    g["Share"] = g["Customers"] / total
    # tri sur l'ordre canonique des segments
    g["__order"] = g["Segment"].map({s: i for i, s in enumerate(SEGMENT_ORDER)})
    g = g.sort_values("__order").drop(columns="__order").reset_index(drop=True)
    g["Recommendation"] = g["Segment"].map(SEGMENT_RECOMMENDATIONS)
    return g
