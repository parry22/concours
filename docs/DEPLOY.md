# Deploying Concours

One VM runs everything with Docker Compose: Postgres, the API, the worker (improvement rounds in Docker), the
web app and Caddy (HTTPS from Let's Encrypt). Files: `deploy/`.

```
browser ──https──▶ caddy ──/api/*──▶ api (FastAPI, 2 processes) ──▶ postgres
                         └─────────▶ web (Next.js)
                    worker ◀── jobs in postgres ── api
                    worker ──docker.sock──▶ solver + referee containers (one round at a time)
```

## 1. The VM

- Ubuntu 24.04 (or any Linux with Docker Engine 24+ and the compose plugin).
- 8 vCPU, 32 GB RAM, 200 GB SSD for a pilot. A round uses 2 CPUs and 2 GB for the solver, protection reads the
  whole file into memory (about 3 GB for 1.75 million payments), and the sample data alone is 250 MB.
- Turn on the provider's disk encryption. Concours encrypts the files that hold real IDs itself (below), but the
  database and the protected splits rely on the disk.
- Open ports 80 and 443 only. SSH by key.
- A DNS A record for your domain pointing at the VM.

## 2. First deploy

```bash
git clone <your repo> /opt/concours && cd /opt/concours
cp deploy/env.production.example deploy/.env
# fill in CONCOURS_DOMAIN, ACME_EMAIL, POSTGRES_PASSWORD, CONCOURS_DATA_KEY, DOCKER_GID (stat -c %g /var/run/docker.sock)
sudo mkdir -p /srv/concours && sudo chown 10001 /srv/concours
python3 scripts/fetch_data.py fraud && python3 scripts/inject_drift.py   # optional: the sample data
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
curl -fsS https://<your domain>/api/readyz        # {"ready": true, "database": "ok", "docker": "ok"}
```

The API refuses to start in production without Postgres, a data key, HTTPS-only cookies and sign-in on.

## 3. The first account

Open `https://<your domain>`. The first visitor creates the owner account and the organisation
(`CONCOURS_SIGNUP=first`), so do this right after the first deploy. Everyone else joins through an invite link
the owner creates under Account. API keys for the command line are under Account too.

Operator commands on the VM:

```bash
docker compose -f deploy/docker-compose.yml exec api python -m app.admin users
docker compose -f deploy/docker-compose.yml exec api python -m app.admin reset-password someone@company.com
docker compose -f deploy/docker-compose.yml exec api python -m app.admin revoke-keys someone@company.com
```

There is no email sending, so password resets go through the operator.

## 4. Updates

```bash
cd /opt/concours && git pull
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

New database columns are added on start. The worker finishes a running round before it stops (15 minutes grace);
a round cut off anyway is marked failed with a note and can be started again.

## 5. Backups and restore

`deploy/backup.sh /backups` writes a Postgres dump and an archive of the workspace, and keeps 14 days. Run it from
cron and copy `/backups` off the VM. The data key is deliberately not in the archive: keep it in your password
manager. Without it, uploads and the ID map cannot be read.

Restore on a fresh VM: deploy as above with the same `CONCOURS_DATA_KEY`, stop `api` and `worker`, then

```bash
docker compose -f deploy/docker-compose.yml exec -T db pg_restore -U concours -d concours --clean < concours-db-<stamp>.dump
tar -C /srv/concours -xzf concours-workspace-<stamp>.tgz
docker compose -f deploy/docker-compose.yml up -d
```

## 6. Monitoring

- `GET /api/healthz` (process up) and `GET /api/readyz` (database and Docker reachable) for an uptime checker.
- Logs are one JSON line per request with a request id (`X-Request-ID` is returned on every response):
  `docker compose -f deploy/docker-compose.yml logs -f api worker`.
- A round stuck in "running" means the worker died: the next worker start fails it after 2 minutes without a
  heartbeat.

## 7. Security notes

- The worker and the API mount `/var/run/docker.sock`. That is root-equivalent on the VM: run nothing else on it.
  Solver containers have no network access except the referee's internal network, 2 CPUs and 2 GB each, and run
  as a non-root user.
- Raw uploads are encrypted while they wait for column mapping and deleted after it. Card-number columns are
  dropped before anything is written. The canonical dataset, the ID map and recent payments are encrypted with
  `CONCOURS_DATA_KEY`. Files given to solvers hold only salted hashes of IDs.
- Passwords are hashed with scrypt; sessions and API keys are stored as SHA-256 hashes. Sign-in attempts are
  limited to 10 per 5 minutes per address in each API process.
- This is not a PCI DSS assessment. If customers may upload card numbers, have the deployment reviewed.
