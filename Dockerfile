# syntax=docker/dockerfile:1
FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN --mount=type=secret,id=vnstock_index \
    PIP_EXTRA_INDEX_URL="$(cat /run/secrets/vnstock_index)" \
    pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY datasource ./datasource
COPY analysis ./analysis
COPY ui ./ui
COPY engine ./engine
COPY filters ./filters
COPY storage ./storage
COPY ingestion ./ingestion
COPY filter_runner ./filter_runner
COPY alert_dispatcher ./alert_dispatcher
COPY config ./config
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
