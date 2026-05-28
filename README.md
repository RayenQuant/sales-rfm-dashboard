# Dashboard Performance Ventes & Segmentation Client

> Pipeline analytique end-to-end sur 500 000+ transactions e-commerce :
> ingestion SQL → nettoyage → KPI exécutifs → segmentation RFM → simulation commerciale.
> Application web interactive déployée et utilisable en un clic.

** Démo live :** (https://rayenquant-dashboard.streamlit.app/)


---

## Aperçu

| Vue Exécutive | Analyse Client | Simulateur Commercial |
| ------------- | -------------- | --------------------- |
| KPI cards (CA, AOV, MoM), tendance mensuelle, top pays & produits | Segmentation RFM 11 segments, recommandations marketing | Slider de variation tarifaire, projection CA/marge |

---

## Ce que démontre ce projet

| Compétence                          | Mise en pratique                                                                    |
| ----------------------------------- | ----------------------------------------------------------------------------------- |
| **Data engineering**                | Pipeline ETL Python avec ingestion CSV → SQLite, indexation, schéma relationnel    |
| **SQL**                             | Vues analytiques avec `WINDOW`, `LAG`, `JULIANDAY`, agrégations conditionnelles   |
| **Data analysis**                   | KPI exécutifs, croissance MoM, top N produits, métriques de cohorte                |
| **Modélisation client (RFM)**       | Quintiles robustes (gestion ex-aequos), mapping vers 11 segments métiers           |
| **Modélisation économique**         | Simulation tarifaire avec élasticité prix-demande et marge brute                   |
| **Product engineering**             | App Streamlit responsive, filtres dynamiques, cache, recommandations contextuelles |
| **Code quality**                    | Architecture modulaire (`src/`), typing, logging, tests, Dockerfile                |

---

## Données

Le projet est conçu pour le **UCI Online Retail Dataset** (~541 909 transactions e-commerce UK, 2010-2011) :

- **Source officielle** : https://archive.ics.uci.edu/ml/datasets/online+retail
- **Mirror Kaggle** : https://www.kaggle.com/datasets/carrie1/ecommerce-data

Pour faciliter le test immédiat, un **générateur de données synthétiques** (`scripts/generate_sample_data.py`) reproduit fidèlement la structure du dataset original (46k+ lignes, ~5 000 clients, 18 pays, annulations, anomalies). À remplacer par le fichier officiel pour les analyses définitives.

---

## Démarrage rapide

```bash
# 1. Cloner et installer
git clone https://github.com/RayenQuant/sales-rfm-dashboard.git
cd sales-rfm-dashboard
pip install -r requirements.txt

# 2. Générer le jeu de données échantillon (ou copier le CSV UCI dans data/online_retail.csv)
python scripts/generate_sample_data.py

# 3. Construire la base SQLite
python -m src.etl --csv data/online_retail.csv --db data/retail.db

# 4. Lancer l'application
streamlit run app.py
```

L'application est accessible sur **http://localhost:8501**.

---

## Avec Docker

```bash
docker build -t sales-rfm-dashboard .
docker run -p 8501:8501 sales-rfm-dashboard
```


---

## 🏗️ Architecture

```
sales-rfm-dashboard/
├── app.py                      # Application Streamlit (3 onglets)
├── src/
│   ├── etl.py                  # Pipeline ETL : CSV → nettoyage → SQLite
│   ├── data_loader.py          # Couche d'accès aux données (SQL)
│   ├── kpis.py                 # KPI exécutifs + simulation tarifaire
│   └── rfm.py                  # Segmentation RFM (scoring + mapping métier)
├── sql/
│   └── analytics_views.sql     # Vues SQL analytiques (audit + BI)
├── scripts/
│   └── generate_sample_data.py # Générateur de données échantillon
├── tests/
│   └── test_pipeline.py        # Tests unitaires (pytest)
├── data/
│   ├── online_retail.csv       # Données brutes (générées ou UCI)
│   └── retail.db               # Base SQLite (créée par l'ETL)
├── .streamlit/
│   └── config.toml             # Thème Streamlit
├── Dockerfile
├── requirements.txt
└── README.md
```

### Flux de données

```
CSV brut
   │
   ▼  src/etl.py : nettoyage (annulations, outliers, anomalies)
SQLite (transactions + customers + index)
   │
   ▼  src/data_loader.py : requêtes filtrées (période, pays)
DataFrame Pandas
   │
   ├─► src/kpis.py    ─►  Tab Vue Exécutive
   ├─► src/rfm.py     ─►  Tab Analyse Client
   └─► simulation     ─►  Tab Simulateur Commercial
```

---

##  Notes méthodologiques

### Nettoyage

- Lignes à **prix unitaire ≤ 0** supprimées (anomalies de saisie).
- Lignes à **quantité > p99.5** retirées (outliers de gros volume difficiles à interpréter).
- Lignes sans **CustomerID** conservées pour les KPI globaux mais exclues de la segmentation RFM.
- Annulations (`InvoiceNo` commençant par `C`) flaguées et intégrées au CA net via leur quantité négative.

### Segmentation RFM

- **Recency**, **Frequency**, **Monetary** calculés par client sur les transactions valides.
- Chaque dimension scorée 1-5 via `qcut` sur le **rang** (gère proprement les ex-aequos).
- 11 segments métiers via un mapping explicite des combinaisons `(R, F, M)` — méthodologie standard issue de la littérature CRM.

### Simulation tarifaire

- Élasticité prix-demande : **-1.2** (hausse de prix → baisse modérée des volumes).
- COGS paramétrable (défaut **55 %** du prix actuel).
- Affichage parallèle de l'impact sur **CA** et **marge brute** — la marge réagit plus fortement car le coût unitaire reste fixe.

---

##  Tests

```bash
pip install pytest
pytest tests/ -v
```

Couvre : pipeline ETL, calcul des KPI, scoring RFM, simulation tarifaire.

---

## 📝 Licence

MIT.
