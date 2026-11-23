#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ! -x .venv/bin/python ]]; then
  printf 'Run bash install_linux.sh first.\n' >&2
  exit 1
fi
if [[ $# -eq 0 ]]; then
  if [[ -f examples/S004_I02_manual.studio.json && -f examples/S004_I02_R01_BVH.bvh && -f examples/S004_I02_R02_BVH.bvh ]]; then
    exec .venv/bin/python -m annotationstudio --manual-example
  fi
  exec .venv/bin/python -m annotationstudio
elif [[ $1 == --* ]]; then
  exec .venv/bin/python -m annotationstudio "$@"
else
  exec .venv/bin/python -m annotationstudio --project "$@"
fi
