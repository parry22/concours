# Brief PLAYER image (the solver submission server). Vendored gym_v1, FROM python:3.12-slim, uid 1000.
# Build context = the competition folder (this repo root):
#   docker build -f player/Dockerfile -t brief-player .
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app /data && chown -R 1000:1000 /app /data
WORKDIR /app

RUN pip install --no-cache-dir --root-user-action=ignore \
    "numpy==2.2.6" "pandas==2.3.3" "scikit-learn==1.7.2" "lightgbm==4.6.0" "xgboost==3.0.5" \
    && apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

COPY player/gym_v1/ /app/gym_v1/
COPY player/common/ /app/common/
COPY player/launch.py /app/launch.py
# Public train split + transform.json. Treated as exposable: train data is public by design.
COPY player/data/ /app/data/

USER 1000
CMD ["python", "/app/launch.py", "--port", "8000"]
