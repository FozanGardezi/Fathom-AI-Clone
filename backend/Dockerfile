# syntax=docker/dockerfile:1.7

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — builder: compile wheels into a self-contained virtualenv.
#
# Build tooling (gcc, headers) lives ONLY in this stage, so none of it ships in
# the final image. python:3.13-slim is used rather than Alpine on purpose:
# Alpine's musl libc has no manylinux wheels, so psycopg/cryptography would be
# compiled from source - slower builds and a *larger* image in practice.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# build-essential: for any sdist that still needs a compiler.
# libpq-dev: Postgres client headers (psycopg[binary] ships its own libpq, but
# this keeps the build working if the pin is ever switched to plain psycopg).
RUN apt-get update && apt-get install --no-install-recommends -y \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# The venv is a single directory, which makes it trivially copyable to stage 2.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Requirements are copied alone first: this layer is cached and only
# invalidated when the pins actually change, not on every source edit.
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && pip install -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime: slim base + the venv + the application code.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings \
    PORT=8000

# Runtime-only packages. libpq5 is the shared library (not the -dev headers);
# curl is used by the container HEALTHCHECK below.
RUN apt-get update && apt-get install --no-install-recommends -y \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Run as an unprivileged user. A container process that is root is root on the
# host kernel if it ever escapes the namespace.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --create-home app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . .

# Static files are collected at build time so the running container needs no
# write access to the image filesystem. Dummy env vars keep Django importable
# during the build - none of them are baked into the final config.
RUN SECRET_KEY=build-only DATABASE_URL=postgres://u:p@localhost:5432/db \
    python manage.py collectstatic --noinput --clear

# Writable paths for user uploads, owned by the app user.
RUN mkdir -p /app/media && chown -R app:app /app/media /app/staticfiles

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/health/" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
