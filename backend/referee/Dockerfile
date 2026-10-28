# Brief REFEREE image: holds hidden leaderboard + holdout data and labels, scores with shared metrics.
# Build context = the competition folder (this repo root):
#   docker build -f referee/Dockerfile -t brief-referee .
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app /data && chown -R 1000:1000 /app /data
WORKDIR /app

RUN pip install --no-cache-dir --root-user-action=ignore "numpy==2.2.6"

COPY referee/gym_v1/ /app/gym_v1/
COPY referee/metrics.py /app/metrics.py
COPY referee/referee.py /app/referee.py
# Hidden data (leaderboard slice, private holdout, labels). This image is never shared with solvers.
COPY referee/data/ /app/data/

USER 1000
CMD ["python", "/app/referee.py"]
