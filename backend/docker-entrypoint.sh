#!/usr/bin/env bash
# Block until Postgres accepts connections, apply migrations, then hand over
# to the CMD (gunicorn, or a Celery worker - both share this entrypoint).
set -euo pipefail

echo "[entrypoint] waiting for the database…"
python - <<'PY'
import os, sys, time
import psycopg

url = os.environ["DATABASE_URL"]
deadline = time.time() + 60
while True:
    try:
        with psycopg.connect(url, connect_timeout=3):
            print("[entrypoint] database is up")
            break
    except Exception as exc:
        if time.time() > deadline:
            sys.exit(f"[entrypoint] database unreachable after 60s: {exc}")
        time.sleep(1)
PY

# Only the web service owns the schema; workers must not race it.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] applying migrations…"
  python manage.py migrate --noinput
fi

exec "$@"
