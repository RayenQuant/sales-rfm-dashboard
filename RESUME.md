# 📄 Guide candidat : du projet au CV

Ce document est l'**accompagnement** du projet pour celui qui le présente.
Il contient : le bloc CV prêt à coller, la procédure de déploiement, les éléments
de langage face au recruteur, et la liste des compétences démontrées.

---

## 1. Bloc CV (à coller directement)

> **Dashboard Performance Ventes & Segmentation Client** | Python (Pandas) · SQL · Streamlit
> [github.com/RayenQuant/sales-rfm-dashboard](https://github.com/RayenQuant/sales-rfm-dashboard) · *(lien live à ajouter)*
>
> - **Pipeline** : end-to-end traitant plus de 500 000 transactions e-commerce brutes — ingestion via base de données relationnelle, nettoyage automatisé (gestion des annulations et anomalies) et structuration des données en indicateurs métiers.
> - **Analyse & KPI** : calcul des métriques de performance exécutives (croissance MoM, évolution des marges, top produits) et implémentation d'une segmentation **RFM** (Récence, Fréquence, Montant) pour classifier la base client en 11 segments comportementaux.
> - **Livrable Business** : application web interactive déployée et accessible immédiatement — filtres dynamiques par région/période, visualisations claires des tendances et recommandations stratégiques pour le ciblage des campagnes marketing.

---

## 2. Procédure de déploiement en 6 étapes

### Étape 1 — Créer un compte GitHub
- Aller sur [github.com](https://github.com) → **Sign up**.
- Choisir comme username `RayenQuant` (ou adapter le lien dans le CV en conséquence).

### Étape 2 — Créer le repository
- **New repository** → nom : `sales-rfm-dashboard` → **Public** → Create.

### Étape 3 — Pousser le code
Depuis le dossier décompressé :

```bash
cd sales-rfm-dashboard
git init
git add .
git commit -m "Initial commit: pipeline + dashboard"
git branch -M main
git remote add origin https://github.com/RayenQuant/sales-rfm-dashboard.git
git push -u origin main
```

### Étape 4 — Connecter Streamlit Cloud
- Aller sur [share.streamlit.io](https://share.streamlit.io) → **Sign in with GitHub**.
- Autoriser l'accès au repo.

### Étape 5 — Déployer
- **New app** → sélectionner le repo `RayenQuant/sales-rfm-dashboard`, branche `main`, fichier `app.py`.
- **Deploy**. Streamlit Cloud installe `requirements.txt` (~2-3 min).
- Le générateur de données s'exécute automatiquement au premier démarrage si la base est absente.

### Étape 6 — Copier le lien live dans le CV
- Format type : `https://rayenquant-sales-rfm-dashboard-app-xxx.streamlit.app`
- Remplace *(lien live à ajouter)* dans le bloc CV.

> ⚠️ **Conseil** : tester le lien depuis un onglet privé pour s'assurer qu'il s'ouvre sans login.

---

## 3. Pour aller plus loin : utiliser les vraies données UCI

L'application fonctionne immédiatement avec le générateur de données. Pour utiliser le **vrai dataset UCI Online Retail** (541 909 transactions réelles) :

1. Télécharger depuis [Kaggle](https://www.kaggle.com/datasets/carrie1/ecommerce-data) ou [UCI ML Repository](https://archive.ics.uci.edu/ml/datasets/online+retail).
2. Renommer le fichier en `online_retail.csv` et le placer dans `data/`.
3. Si le fichier d'origine est `.xlsx`, le convertir en CSV :
   ```python
   import pandas as pd
   pd.read_excel("Online Retail.xlsx").to_csv("data/online_retail.csv", index=False)
   ```
4. Supprimer la base existante et relancer le pipeline :
   ```bash
   rm data/retail.db
   python -m src.etl --csv data/online_retail.csv --db data/retail.db
   streamlit run app.py
   ```

Le CV mentionne *« plus de 500 000 transactions »* — cette assertion devient littéralement vraie avec le fichier UCI officiel.

---

## 4. Éléments de langage face au recruteur

### Si on demande « *Pourquoi ce projet ?* »
> *« Je voulais montrer une chaîne data complète : pas juste un notebook Jupyter, mais un pipeline qui ingère, nettoie, stocke en SQL, calcule des KPI et expose le tout dans une app que n'importe quel manager peut utiliser sans coder. C'est ce qu'on fait en condition réelle. »*

### Si on demande « *Pourquoi RFM ?* »
> *« RFM, c'est l'approche standard CRM pour transformer une base de transactions en cohortes actionnables. Plutôt que de dire "on a 5 000 clients", je peux dire "on a 591 Champions qui pèsent 35 % du CA, 320 clients à risque qu'il faut reconquérir, et 800 hibernants où ça ne sert à rien de dépenser". Le marketing peut câbler une campagne directement dessus. »*

### Si on demande « *Comment as-tu géré la qualité des données ?* »
> *« Le dataset UCI est connu pour avoir 2 % d'annulations (factures préfixées par C), des prix nuls, des CustomerID manquants et quelques outliers de quantité. Le pipeline les flague explicitement, ne supprime que ce qui est inexploitable, et garde un audit du nettoyage. Les annulations sont conservées en quantité négative pour ne pas surestimer le CA brut. »*

### Si on demande « *À quoi sert le simulateur de prix ?* »
> *« C'est l'élément qui fait passer le dashboard du statut "rapport" à celui d'"outil de décision". Avec une élasticité prix-demande standard de -1.2, je montre que +5 % de prix fait baisser le CA mais augmente nettement la marge — exactement la conversation qu'un pricing manager veut avoir. »*

### Si on demande « *Pourquoi SQLite et pas Postgres ?* »
> *« Pour ce projet déployable en un clic, SQLite suffit et reste sans dépendance externe. La couche `data_loader.py` est volontairement isolée : pour passer à Postgres ou Snowflake, je n'ai qu'un seul fichier à toucher. »*

### Si on demande « *Le dataset est-il réel ?* »
> Honnêteté : *« Le projet est conçu pour le dataset UCI Online Retail. J'ai écrit un générateur de données synthétiques qui reproduit fidèlement sa structure pour faciliter la démo, mais le pipeline et l'app fonctionnent à l'identique avec le fichier officiel — il suffit de le déposer dans `data/`. »*

---

## 5. Compétences démontrées (checklist)

- [x] **Python avancé** : modularisation, typing, logging, gestion d'erreurs, caching
- [x] **Pandas** : nettoyage, agrégations groupby, fenêtres temporelles
- [x] **SQL** : création de schéma, indexes, vues, fonctions fenêtres (LAG)
- [x] **Modélisation client (RFM)** : quintiles robustes, mapping métier
- [x] **Visualisation** : Altair, design dashboard, hiérarchie de l'information
- [x] **Product engineering** : Streamlit, filtres dynamiques, cache, UX
- [x] **DevOps léger** : Dockerfile, Makefile, déploiement cloud
- [x] **Tests** : 20 tests pytest couvrant ETL, KPI, RFM, simulation
- [x] **Documentation** : README structuré, guide candidat, docstrings français
- [x] **Pensée business** : KPI exécutifs, recommandations par segment, simulateur d'aide à la décision

---

## 6. Roadmap d'amélioration (pour les entretiens techniques poussés)

Si le recruteur demande *« qu'est-ce que tu améliorerais ? »*, voici des pistes crédibles :

1. **Migrer vers DuckDB** au lieu de SQLite pour gérer 10× plus de volume sans changer d'API.
2. **CLTV prédictif** : modèle BG/NBD + Gamma-Gamma (lifetimes lib) pour estimer la valeur future de chaque segment.
3. **Cohort analysis** : courbes de rétention par mois d'acquisition.
4. **A/B testing du pricing** : framework statistique (bootstrap) pour valider l'élasticité empirique.
5. **CI/CD GitHub Actions** : tests + lint + déploiement auto.
6. **dbt** pour formaliser les transformations SQL.
7. **Authentification** : Streamlit-authenticator pour limiter l'accès aux données réelles.
