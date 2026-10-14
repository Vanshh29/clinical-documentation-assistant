# syntax=docker/dockerfile:1.7
# Build context is the repository root:  docker build -f apps/web/Dockerfile .
FROM node:26.3.0-alpine3.22 AS build
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31.6-alpine
# Unprivileged image: runs as uid 101 and listens on 8080.
ENV API_UPSTREAM=http://api:8000
COPY apps/web/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
# The base image already runs as the unprivileged nginx user; say so explicitly.
USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
