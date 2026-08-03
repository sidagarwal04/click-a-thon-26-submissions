#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="${FEATURELENS_LIBRECHAT_DIR:-${project_dir}/.local/librechat}"
upstream_url="https://github.com/danny-avila/LibreChat.git"

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop must be running before LibreChat can start." >&2
  exit 1
fi

if [[ ! -d "${runtime_dir}/.git" ]]; then
  mkdir -p "$(dirname "${runtime_dir}")"
  git clone --depth 1 "${upstream_url}" "${runtime_dir}"
fi

if [[ ! -f "${runtime_dir}/.env" ]]; then
  cp "${runtime_dir}/.env.example" "${runtime_dir}/.env"
  chmod 600 "${runtime_dir}/.env"
fi

export FEATURELENS_LIBRECHAT_CONFIG="${project_dir}/librechat.yaml"
export UID
GID="$(id -g)"
export GID

docker compose \
  --project-directory "${runtime_dir}" \
  -f "${runtime_dir}/docker-compose.yml" \
  -f "${project_dir}/ops/librechat/docker-compose.override.yml" \
  up -d

echo "LibreChat is starting at http://localhost:3080"
echo "The first account registered in this local instance becomes its administrator."
