#!/usr/bin/env bash
set -euo pipefail
studio_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd -- "$studio_root"
trap 'printf "Developer setup failed. Read the error above; no neural weights were requested.\n" >&2' ERR
printf 'Annotation Studio developer setup: isolated .venv, Python 3.11/3.12, 64-bit.\n'
printf 'Internet is required for Python dependencies. No administrator privileges are used.\n'
bash "$studio_root/install_linux.sh"
studio_python="$studio_root/.venv/bin/python"
if [[ ! -x "$studio_python" ]]; then
  printf 'The local .venv Python was not created. Check the base installer output.\n' >&2
  exit 1
fi
"$studio_python" -m pip install -r "$studio_root/requirements-dev.txt"
"$studio_python" -m pip check
"$studio_python" "$studio_root/scripts/doctor.py"
printf '\nDeveloper setup complete. Open this folder in VS Code and read README.md.\n'
printf 'Run tests: .venv/bin/python -m pytest tests -q\n'
