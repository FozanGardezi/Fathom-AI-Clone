# syntax=docker/dockerfile:1.7

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — build the static bundle with Node. Node is a build-time dependency
# only; it never reaches the published image.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:24-alpine AS builder

WORKDIR /app

# package.json + lockfile first so `npm ci` is cached until the deps change.
COPY package.json package-lock.json ./
# `npm ci` installs exactly what the lockfile pins - reproducible, unlike
# `npm install`, which may silently resolve newer versions.
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY . .

# Vite inlines VITE_* variables at build time, so the API base must be known
# here rather than at container start. The default (/api) keeps the browser on
# the same origin and lets nginx proxy it - no CORS preflight in production.
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — serve the bundle with nginx.
#
# nginx-unprivileged runs as a non-root user out of the box; the stock nginx
# image starts as root to bind port 80. Alpine is right here: the final image
# is static files plus nginx, with no native modules to compile.
# ─────────────────────────────────────────────────────────────────────────────
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# nginx.conf is a template so the backend host/port can be injected at start
# time; the base image expands /etc/nginx/templates/*.template on boot.
COPY --chown=nginx:nginx nginx.conf.template /etc/nginx/templates/default.conf.template

COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html

ENV BACKEND_HOST=backend \
    BACKEND_PORT=8000 \
    PORT=3000

# 3000 is above 1024, so an unprivileged process may bind it directly.
EXPOSE 3000

USER nginx

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider "http://127.0.0.1:3000/healthz" || exit 1
