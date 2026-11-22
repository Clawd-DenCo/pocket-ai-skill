#!/usr/bin/env bash
# Compatibility shim: structured JSON and error handling live in the Python CLI.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$script_dir/pocket_api.py" search "${1:-meeting}"
