#!/usr/bin/env bash
set -euo pipefail

mcp_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="${mcp_dir}/arr-mcp"

if [[ ! -f "${project_dir}/pyproject.toml" ]]; then
  echo "Arr MCP submodule is missing. Run: git submodule update --init --recursive" >&2
  exit 1
fi

if command -v uv >/dev/null 2>&1; then
  uv_bin="$(command -v uv)"
elif [[ -x "${HOME}/.local/share/k8s-home/uv/bin/uv" ]]; then
  uv_bin="${HOME}/.local/share/k8s-home/uv/bin/uv"
elif [[ -x "${HOME}/.local/bin/uv" ]]; then
  uv_bin="${HOME}/.local/bin/uv"
else
  echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/." >&2
  exit 1
fi

exec "${uv_bin}" run --locked --project "${project_dir}" arr-mcp
