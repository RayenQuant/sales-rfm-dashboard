.PHONY: help install data db run test clean docker deploy-check

help:
	@echo "Commandes disponibles :"
	@echo "  make install       Installer les dépendances Python"
	@echo "  make data          Générer le CSV d'échantillon"
	@echo "  make db            Lancer l'ETL et construire la base SQLite"
	@echo "  make run           Démarrer l'application Streamlit"
	@echo "  make test          Lancer la suite de tests pytest"
	@echo "  make clean         Supprimer les artefacts régénérables"
	@echo "  make docker        Construire et lancer le conteneur Docker"
	@echo "  make deploy-check  Vérifier que tout est prêt pour Streamlit Cloud"

install:
	pip install -r requirements.txt

data:
	python scripts/generate_sample_data.py

db: data
	python -m src.etl --csv data/online_retail.csv --db data/retail.db

run:
	streamlit run app.py

test:
	pytest tests/ -v

clean:
	rm -rf data/retail.db data/retail.db-journal
	rm -rf __pycache__ src/__pycache__ tests/__pycache__ .pytest_cache

docker:
	docker build -t sales-rfm-dashboard .
	docker run -p 8501:8501 sales-rfm-dashboard

deploy-check:
	@echo "Vérification du repo avant déploiement..."
	@test -f app.py && echo "  ✓ app.py présent"
	@test -f requirements.txt && echo "  ✓ requirements.txt présent"
	@test -f scripts/generate_sample_data.py && echo "  ✓ générateur de données présent"
	@test -f src/etl.py && echo "  ✓ pipeline ETL présent"
	@test -f README.md && echo "  ✓ README.md présent"
	@echo "Prêt pour Streamlit Cloud → https://share.streamlit.io"
