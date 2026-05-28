"""
Dashboard Performance Ventes & Segmentation Client
==================================================

Application Streamlit à trois onglets :

  1. Vue Exécutive       — KPI cards + tendances ventes
  2. Analyse Client      — segmentation RFM
  3. Simulateur Commercial — filtres dynamiques + simulation tarifaire

Lancer :
    streamlit run app.py
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src import data_loader, kpis, rfm

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Sales & RFM Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
/* layout */
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1400px; }

/* hero header */
.hero {
    background: linear-gradient(135deg, #0F4C81 0%, #1E78B6 100%);
    color: #fff;
    padding: 1.6rem 1.8rem;
    border-radius: 14px;
    margin-bottom: 1.4rem;
    box-shadow: 0 8px 24px rgba(15, 76, 129, 0.18);
}
.hero h1 {
    margin: 0;
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}
.hero p {
    margin: 0.35rem 0 0;
    opacity: 0.85;
    font-size: 0.95rem;
}

/* KPI cards */
.kpi-card {
    background: #ffffff;
    border: 1px solid #E4E8F1;
    border-radius: 12px;
    padding: 1.1rem 1.2rem;
    height: 100%;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(15, 76, 129, 0.08);
}
.kpi-label {
    font-size: 0.78rem;
    color: #5A6B85;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.35rem;
    font-weight: 600;
}
.kpi-value {
    font-size: 1.7rem;
    font-weight: 700;
    color: #0E1726;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
.kpi-delta-pos { color: #1E8A4F; font-weight: 600; font-size: 0.85rem; margin-top: 0.35rem; }
.kpi-delta-neg { color: #C0392B; font-weight: 600; font-size: 0.85rem; margin-top: 0.35rem; }
.kpi-delta-neutral { color: #5A6B85; font-weight: 600; font-size: 0.85rem; margin-top: 0.35rem; }

/* tabs */
.stTabs [data-baseweb="tab-list"] { gap: 0.4rem; }
.stTabs [data-baseweb="tab"] {
    padding: 0.55rem 1.1rem;
    border-radius: 8px;
    background: #F4F6FA;
    font-weight: 600;
}
.stTabs [aria-selected="true"] { background: #0F4C81; color: #fff !important; }

/* segment badges */
.seg-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #fff;
}

/* section titles */
.section-title {
    font-size: 1.05rem;
    font-weight: 700;
    margin: 1.4rem 0 0.6rem;
    color: #0E1726;
    letter-spacing: -0.01em;
}

/* recommendations card */
.reco-card {
    background: #F8FAFD;
    border-left: 4px solid #0F4C81;
    padding: 0.8rem 1rem;
    border-radius: 6px;
    margin-bottom: 0.6rem;
}
.reco-segment { font-weight: 700; color: #0F4C81; }
.reco-text { color: #2C3E50; font-size: 0.92rem; margin-top: 0.15rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CURRENCY = "£"  # UCI Online Retail = retailer britannique

SEGMENT_COLORS = {
    "Champions":           "#1E8A4F",
    "Loyal Customers":     "#2EB872",
    "Potential Loyalists": "#7EC8A9",
    "New Customers":       "#5DADE2",
    "Promising":           "#85C1E9",
    "Need Attention":      "#F39C12",
    "About to Sleep":      "#E67E22",
    "At Risk":             "#E74C3C",
    "Cannot Lose Them":    "#922B21",
    "Hibernating":         "#7F8C8D",
    "Lost":                "#34495E",
}


def fmt_money(x: float) -> str:
    return f"{CURRENCY}{x:,.0f}"


def fmt_pct(x: float) -> str:
    return f"{x*100:+.1f}%"


def kpi_card(label: str, value: str, delta: str | None = None, delta_kind: str = "neutral"):
    delta_html = ""
    if delta is not None:
        cls = {"pos": "kpi-delta-pos", "neg": "kpi-delta-neg", "neutral": "kpi-delta-neutral"}[delta_kind]
        arrow = {"pos": "▲", "neg": "▼", "neutral": "■"}[delta_kind]
        delta_html = f'<div class="{cls}">{arrow}  {delta}</div>'
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def _load_data_cached(countries: tuple[str, ...] | None, start: str | None, end: str | None):
    return data_loader.load_transactions(
        countries=list(countries) if countries else None,
        start_date=start,
        end_date=end,
    )


@st.cache_data(show_spinner=False)
def _bootstrap():
    """Lance le pipeline ETL si la base SQLite n'existe pas, puis renvoie les bornes."""
    data_loader.ensure_database()
    return data_loader.list_countries(), data_loader.date_bounds()


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="hero">
        <h1>Dashboard Performance Ventes & Segmentation Client</h1>
        <p>Pipeline end-to-end : ingestion SQL · nettoyage · KPI exécutifs · segmentation RFM · simulation commerciale</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Bootstrap base + sidebar filters
# ---------------------------------------------------------------------------

try:
    all_countries, (min_date, max_date) = _bootstrap()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

min_d = dt.datetime.fromisoformat(min_date).date()
max_d = dt.datetime.fromisoformat(max_date).date()

with st.sidebar:
    st.header("Filtres")
    st.caption("Les filtres s'appliquent à tous les onglets en temps réel.")

    date_range = st.date_input(
        "Période",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
        format="YYYY-MM-DD",
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
    else:
        start_d, end_d = min_d, max_d

    countries_default = ["United Kingdom"] if "United Kingdom" in all_countries else all_countries[:1]
    countries_sel = st.multiselect(
        "Pays",
        options=all_countries,
        default=all_countries,  # par défaut on charge tout, l'utilisateur filtre ensuite
        help="Sélectionner un ou plusieurs marchés.",
    )

    st.divider()
    st.caption(
        "💡 **Données** : 46k transactions e-commerce générées sur le format "
        "du UCI Online Retail Dataset. Remplaçables par le fichier officiel."
    )


# ---------------------------------------------------------------------------
# Chargement filtré
# ---------------------------------------------------------------------------

df = _load_data_cached(
    tuple(countries_sel) if countries_sel else None,
    start_d.isoformat(),
    end_d.isoformat(),
)

if df.empty:
    st.warning("Aucune transaction ne correspond aux filtres. Élargis la plage de dates ou la liste de pays.")
    st.stop()


# ---------------------------------------------------------------------------
# Onglets
# ---------------------------------------------------------------------------

tab_exec, tab_client, tab_sim = st.tabs([
    "Vue Exécutive",
    "Analyse Client",
    "Simulateur Commercial",
])


# ===========================================================================
# TAB 1 — Vue Exécutive
# ===========================================================================

with tab_exec:
    k = kpis.headline_kpis(df)
    mom = kpis.mom_growth(df)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Chiffre d'affaires net", fmt_money(k["net_revenue"]),
                 delta=f"Taux d'annulation : {k['cancellation_rate']*100:.1f}%",
                 delta_kind="neutral")
    with c2:
        kpi_card("Commandes", f"{k['n_orders']:,}".replace(",", " "))
    with c3:
        kpi_card("Panier moyen (AOV)", fmt_money(k["aov"]))
    with c4:
        kpi_card("Croissance MoM", fmt_pct(mom) if mom else "—",
                 delta="Dernier mois clos vs précédent",
                 delta_kind="pos" if mom > 0 else "neg" if mom < 0 else "neutral")

    cc1, cc2 = st.columns(2)
    with cc1:
        kpi_card("Clients uniques", f"{k['n_customers']:,}".replace(",", " "))
    with cc2:
        kpi_card("Unités vendues", f"{k['units_sold']:,}".replace(",", " "))

    # ---- Tendance mensuelle ------------------------------------------------
    st.markdown('<div class="section-title">Évolution mensuelle du chiffre d\'affaires</div>',
                unsafe_allow_html=True)

    monthly = kpis.monthly_revenue(df)
    monthly["MonthDate"] = pd.to_datetime(monthly["YearMonth"] + "-01")
    monthly["RevenueFmt"] = monthly["Revenue"].apply(fmt_money)

    line = (
        alt.Chart(monthly)
        .mark_line(point=alt.OverlayMarkDef(size=70, filled=True, color="#0F4C81"),
                   color="#0F4C81", strokeWidth=2.5)
        .encode(
            x=alt.X("MonthDate:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=-30)),
            y=alt.Y("Revenue:Q", title="Chiffre d'affaires (£)",
                    axis=alt.Axis(format=",.0f")),
            tooltip=[
                alt.Tooltip("YearMonth:N", title="Mois"),
                alt.Tooltip("Revenue:Q", title="CA", format=",.0f"),
                alt.Tooltip("MoM:Q", title="MoM", format="+.1%"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(line, use_container_width=True)

    # ---- Top pays & produits ----------------------------------------------
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<div class="section-title">Top 10 pays (CA net)</div>',
                    unsafe_allow_html=True)
        top_c = kpis.top_countries(df, 10)
        chart = (
            alt.Chart(top_c)
            .mark_bar(color="#0F4C81", cornerRadiusEnd=4)
            .encode(
                y=alt.Y("Country:N", sort="-x", title=None),
                x=alt.X("Revenue:Q", title="CA (£)", axis=alt.Axis(format=",.0f")),
                tooltip=[
                    alt.Tooltip("Country:N", title="Pays"),
                    alt.Tooltip("Revenue:Q", title="CA", format=",.0f"),
                    alt.Tooltip("Orders:Q", title="Commandes", format=",.0f"),
                ],
            )
            .properties(height=380)
        )
        st.altair_chart(chart, use_container_width=True)

    with col_right:
        st.markdown('<div class="section-title">Top 10 produits (CA net)</div>',
                    unsafe_allow_html=True)
        top_p = kpis.top_products(df, 10)
        top_p["Label"] = top_p["Description"].str.slice(0, 35)
        chart_p = (
            alt.Chart(top_p)
            .mark_bar(color="#1E78B6", cornerRadiusEnd=4)
            .encode(
                y=alt.Y("Label:N", sort="-x", title=None),
                x=alt.X("Revenue:Q", title="CA (£)", axis=alt.Axis(format=",.0f")),
                tooltip=[
                    alt.Tooltip("Description:N", title="Produit"),
                    alt.Tooltip("StockCode:N", title="Code"),
                    alt.Tooltip("Revenue:Q", title="CA", format=",.0f"),
                    alt.Tooltip("Units:Q", title="Unités", format=",.0f"),
                ],
            )
            .properties(height=380)
        )
        st.altair_chart(chart_p, use_container_width=True)


# ===========================================================================
# TAB 2 — Analyse Client (RFM)
# ===========================================================================

with tab_client:
    st.markdown(
        "**Méthodologie RFM** — chaque client est noté de 1 à 5 sur trois axes : "
        "**R**écence (jours depuis le dernier achat), **F**réquence (nombre de commandes) "
        "et **M**ontant (CA cumulé). Le triplet est ensuite traduit en segment métier."
    )

    rfm_raw = rfm.compute_rfm(df)
    scored = rfm.score_rfm(rfm_raw)
    summary = rfm.segment_summary(scored)

    if scored.empty:
        st.info("Pas de client identifié sur la sélection — élargis les filtres.")
    else:
        # --- KPIs RFM -------------------------------------------------------
        c1, c2, c3, c4 = st.columns(4)
        n_total = len(scored)
        n_champ = (scored["Segment"] == "Champions").sum()
        n_at_risk = scored["Segment"].isin(["At Risk", "Cannot Lose Them"]).sum()
        n_hib = scored["Segment"].isin(["Hibernating", "Lost", "About to Sleep"]).sum()

        with c1:
            kpi_card("Clients analysés", f"{n_total:,}".replace(",", " "))
        with c2:
            kpi_card("Champions", f"{n_champ:,}".replace(",", " "),
                     delta=f"{n_champ/n_total*100:.1f}% de la base",
                     delta_kind="pos")
        with c3:
            kpi_card("À risque", f"{n_at_risk:,}".replace(",", " "),
                     delta=f"{n_at_risk/n_total*100:.1f}% de la base",
                     delta_kind="neg")
        with c4:
            kpi_card("En sommeil / perdus", f"{n_hib:,}".replace(",", " "),
                     delta=f"{n_hib/n_total*100:.1f}% de la base",
                     delta_kind="neutral")

        # --- Distribution segments -----------------------------------------
        st.markdown('<div class="section-title">Distribution des segments</div>',
                    unsafe_allow_html=True)

        col_left, col_right = st.columns([3, 2])

        with col_left:
            chart_seg = (
                alt.Chart(summary)
                .mark_bar(cornerRadiusEnd=4)
                .encode(
                    y=alt.Y("Segment:N", sort=rfm.SEGMENT_ORDER, title=None),
                    x=alt.X("Customers:Q", title="Nombre de clients"),
                    color=alt.Color(
                        "Segment:N",
                        scale=alt.Scale(
                            domain=list(SEGMENT_COLORS.keys()),
                            range=list(SEGMENT_COLORS.values()),
                        ),
                        legend=None,
                    ),
                    tooltip=[
                        alt.Tooltip("Segment:N"),
                        alt.Tooltip("Customers:Q", title="Clients", format=",.0f"),
                        alt.Tooltip("Share:Q", title="Part", format=".1%"),
                        alt.Tooltip("AvgMonetary:Q", title="Monétaire moyen (£)", format=",.0f"),
                        alt.Tooltip("TotalMonetary:Q", title="CA total (£)", format=",.0f"),
                    ],
                )
                .properties(height=420)
            )
            st.altair_chart(chart_seg, use_container_width=True)

        with col_right:
            st.markdown('<div class="section-title">Valeur économique par segment</div>',
                        unsafe_allow_html=True)
            disp = summary.copy()
            disp["Part"] = disp["Share"].apply(lambda x: f"{x*100:.1f}%")
            disp["Monétaire moyen"] = disp["AvgMonetary"].apply(fmt_money)
            disp["CA total"] = disp["TotalMonetary"].apply(fmt_money)
            st.dataframe(
                disp[["Segment", "Customers", "Part", "Monétaire moyen", "CA total"]]
                .rename(columns={"Customers": "Clients"}),
                hide_index=True,
                use_container_width=True,
                height=420,
            )

        # --- Recommandations -----------------------------------------------
        st.markdown('<div class="section-title">Recommandations stratégiques par segment</div>',
                    unsafe_allow_html=True)

        for _, row in summary.iterrows():
            st.markdown(
                f"""
                <div class="reco-card">
                    <span class="seg-badge" style="background:{SEGMENT_COLORS.get(row['Segment'], '#0F4C81')}">
                        {row['Segment']}
                    </span>
                    <span style="margin-left:0.6rem;color:#5A6B85;font-size:0.85rem">
                        {row['Customers']:,} clients · monétaire moyen {fmt_money(row['AvgMonetary'])}
                    </span>
                    <div class="reco-text">{row['Recommendation']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # --- Table détaillée (téléchargeable) ------------------------------
        with st.expander("Voir le détail client par client (table téléchargeable)"):
            scored_display = scored.copy()
            scored_display["Monetary"] = scored_display["Monetary"].round(2)
            st.dataframe(scored_display, hide_index=True, use_container_width=True, height=320)
            st.download_button(
                "⬇Exporter en CSV",
                scored_display.to_csv(index=False).encode("utf-8"),
                file_name="rfm_segmentation.csv",
                mime="text/csv",
            )


# ===========================================================================
# TAB 3 — Simulateur Commercial
# ===========================================================================

with tab_sim:
    st.markdown(
        "Évalue l'impact d'une variation tarifaire sur le chiffre d'affaires et la marge. "
        "Le modèle suppose un **COGS** ajustable et une **élasticité prix-demande** de -1.2 "
        "(une hausse de prix réduit la quantité vendue)."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        price_change = st.slider(
            "Variation tarifaire (%)",
            min_value=-15, max_value=25, value=5, step=1,
            help="Hausse ou baisse appliquée à l'ensemble des prix unitaires.",
        )
    with col_b:
        cogs_pct = st.slider(
            "Coût des marchandises vendues (% du prix actuel)",
            min_value=20, max_value=80, value=55, step=5,
            help="Hypothèse de COGS. La marge brute = CA - COGS.",
        )

    sim = kpis.simulate_price_change(df, price_change / 100, cogs_ratio=cogs_pct / 100)

    rev_delta_pct = sim["delta_revenue"] / sim["current_revenue"] if sim["current_revenue"] else 0
    margin_delta_pct = sim["delta_margin"] / sim["current_margin"] if sim["current_margin"] else 0

    st.markdown('<div class="section-title">Projection</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("CA actuel", fmt_money(sim["current_revenue"]))
    with c2:
        kpi_card("CA simulé", fmt_money(sim["new_revenue"]),
                 delta=fmt_pct(rev_delta_pct),
                 delta_kind="pos" if sim["delta_revenue"] >= 0 else "neg")
    with c3:
        kpi_card("Marge actuelle", fmt_money(sim["current_margin"]))
    with c4:
        kpi_card("Marge simulée", fmt_money(sim["new_margin"]),
                 delta=fmt_pct(margin_delta_pct),
                 delta_kind="pos" if sim["delta_margin"] >= 0 else "neg")

    # --- Visualisation comparative -----------------------------------------
    comp = pd.DataFrame({
        "Scénario": ["Actuel", "Simulé", "Actuel", "Simulé"],
        "Métrique": ["Chiffre d'affaires", "Chiffre d'affaires", "Marge brute", "Marge brute"],
        "Valeur": [
            sim["current_revenue"], sim["new_revenue"],
            sim["current_margin"], sim["new_margin"],
        ],
    })
    chart = (
        alt.Chart(comp)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("Scénario:N", title=None),
            y=alt.Y("Valeur:Q", title="£", axis=alt.Axis(format=",.0f")),
            color=alt.Color(
                "Scénario:N",
                scale=alt.Scale(domain=["Actuel", "Simulé"], range=["#94A3B8", "#0F4C81"]),
                legend=None,
            ),
            column=alt.Column("Métrique:N", title=None, header=alt.Header(labelFontSize=13, labelFontWeight="bold")),
            tooltip=[
                alt.Tooltip("Scénario:N"),
                alt.Tooltip("Métrique:N"),
                alt.Tooltip("Valeur:Q", title="£", format=",.0f"),
            ],
        )
        .properties(height=340, width=260)
    )
    st.altair_chart(chart, use_container_width=False)

    # --- Lecture business ---------------------------------------------------
    st.markdown('<div class="section-title">Lecture business</div>', unsafe_allow_html=True)
    qty_factor = sim["qty_factor"]
    if price_change > 0:
        msg = (
            f"À **+{price_change}%** de prix, on table sur une baisse de **{(1-qty_factor)*100:.1f}%** "
            f"des volumes (élasticité -1.2). "
            f"L'effet net sur le **CA** est {'**positif**' if sim['delta_revenue'] >= 0 else '**négatif**'} "
            f"({fmt_pct(rev_delta_pct)}), mais la **marge** "
            f"{'progresse' if sim['delta_margin'] >= 0 else 'recule'} de **{fmt_pct(margin_delta_pct)}** "
            "car le coût unitaire reste fixe. Le levier prix est généralement plus puissant sur la marge que sur le CA."
        )
    elif price_change < 0:
        msg = (
            f"À **{price_change}%** de prix, on anticipe un gain de volume de **{(qty_factor-1)*100:.1f}%**. "
            f"Le CA évolue de **{fmt_pct(rev_delta_pct)}** ; la marge unitaire baisse, "
            f"d'où une marge totale en variation de **{fmt_pct(margin_delta_pct)}**. "
            "À envisager comme outil de conquête, pas comme arme par défaut."
        )
    else:
        msg = "Aucune variation appliquée — bouge le curseur pour simuler un scénario."
    st.info(msg)

    # --- Bornes des filtres actifs -----------------------------------------
    with st.expander("Périmètre de la simulation"):
        st.write(f"- **Période** : du {start_d} au {end_d}")
        st.write(f"- **Pays inclus** : {len(countries_sel)} pays ({', '.join(countries_sel[:5])}{'...' if len(countries_sel) > 5 else ''})")
        st.write(f"- **Transactions** : {len(df):,}")
        st.write(f"- **Hypothèses** : élasticité -1.2, COGS = {cogs_pct}% du prix actuel")


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="margin-top:3rem;padding-top:1.2rem;border-top:1px solid #E4E8F1;
                color:#5A6B85;font-size:0.82rem;text-align:center">
        Pipeline Python · SQLite · Streamlit ·
        <a href="https://github.com/RayenQuant/sales-rfm-dashboard"
           style="color:#0F4C81;text-decoration:none;font-weight:600">
            Source GitHub
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)
