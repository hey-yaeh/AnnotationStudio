#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")"
trap 'printf "Installation failed. Check the message above.\n" >&2' ERR
if [[ ! -x .venv/bin/python ]]; then
  studio_python=""
  for candidate in python3.11 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys,struct; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize("P")==8 else 1)'; then
      studio_python="$candidate"
      break
    fi
  done
  if [[ -z "$studio_python" ]]; then
    printf 'Install 64-bit Python 3.11 or 3.12 with venv first.\n' >&2
    exit 1
  fi
  "$studio_python" -m venv .venv
fi
.venv/bin/python -c 'import sys,struct; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize("P")==8 else 1)'
.venv/bin/python -m pip install --upgrade 'pip>=24'
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
printf 'Annotation Studio 0.5.4 installed. Run: bash run_linux.sh\n'
