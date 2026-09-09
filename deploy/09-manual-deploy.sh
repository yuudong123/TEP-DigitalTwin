#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
COMPOSE_FILE="${PROJECT_DIR}/compose.yaml"
ENV_FILE="${PROJECT_DIR}/.env"

fail() {
    echo "[ERROR] $*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 \
        || fail "Required command not found: $1"
}

require_command docker

docker compose version >/dev/null 2>&1 \
    || fail "Docker Compose v2 is required."

docker info >/dev/null 2>&1 \
    || fail "Docker daemon is unavailable or the current user lacks Docker access."

[[ -f "${COMPOSE_FILE}" ]] \
    || fail "compose.yaml not found: ${COMPOSE_FILE}"

[[ -f "${ENV_FILE}" ]] \
    || fail ".env not found. Copy .env.example and set server values first."

cd "${PROJECT_DIR}"

echo "[CHECK] Validating Compose configuration"
docker compose config --quiet

echo "[DEPLOY] Building images and starting services"
docker compose up --build --detach

echo "[STATUS]"
docker compose ps --all

cat <<'EOF'

[NEXT] Inspect service logs before treating this deployment as successful:
  docker compose logs --tail 100 kafka
  docker compose logs --tail 100 api inference monitor

The API, inference, and monitor services require their implementations from
sections 12, 13, and 17. Until then, their containers are expected to fail.
EOF
