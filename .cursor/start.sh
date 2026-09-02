#!/usr/bin/env bash
# Cloud Agent start: bring up PostgreSQL and ensure the app role/database exist.
# Runs on every boot; must be idempotent and return promptly.
set -euo pipefail

echo "[start] Starting PostgreSQL cluster (16/main)..."
# Returns non-zero if the cluster is already running — that's fine.
sudo pg_ctlcluster 16 main start 2>/dev/null || true

echo "[start] Waiting for PostgreSQL to accept connections..."
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then
    break
  fi
  sleep 1
done

echo "[start] Ensuring 'reimagine' role and 'reimagine_ai' database exist..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='reimagine'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE reimagine WITH LOGIN SUPERUSER PASSWORD 'reimagine';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='reimagine_ai'" | grep -q 1 \
  || sudo -u postgres createdb -O reimagine reimagine_ai

echo "[start] PostgreSQL ready on 127.0.0.1:5432 (db=reimagine_ai)."
