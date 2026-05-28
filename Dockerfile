FROM python:3.11-slim

WORKDIR /app

# system deps (sqlite is included in base image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# code
COPY . .

# generate sample data + build SQLite at build time
RUN python scripts/generate_sample_data.py && \
    python -m src.etl --csv data/online_retail.csv --db data/retail.db

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
