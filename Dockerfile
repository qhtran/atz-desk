# syntax=docker/dockerfile:1
FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN --mount=type=secret,id=vnstock_index \
    PIP_EXTRA_INDEX_URL="$(cat /run/secrets/vnstock_index)" \
    pip install --no-cache-dir -r requirements.txt
# Package Python nằm dưới src/atz; YAML runtime ở /app/config
ENV PYTHONPATH=/app/src/atz
COPY src ./src
COPY config ./config
COPY frontend/debug-overlay.js frontend/debug-overlay.css frontend/ui_catalog_atz.json ./src/atz/static/
EXPOSE 8501
CMD ["streamlit", "run", "src/atz/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
