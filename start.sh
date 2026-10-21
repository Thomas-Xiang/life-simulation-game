#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
VENV="$ROOT/backend/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  BOOTSTRAP=""
  for candidate in python3.13 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys;raise SystemExit(sys.version_info<(3,12))' 2>/dev/null; then
      BOOTSTRAP="$(command -v "$candidate")";break
    fi
  done
  if [[ -z "$BOOTSTRAP" ]]; then echo "Install Python 3.12+ first." >&2;exit 1;fi
  "$BOOTSTRAP" -m venv "$VENV"
fi
PYTHON="$VENV/bin/python"
"$PYTHON" -c 'import sys;assert sys.version_info>=(3,12), "Recreate backend/.venv with Python 3.12+"'
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1;then
 echo "Install Node.js 22.12+ and npm first." >&2;exit 1
fi
node -e 'const [a,b]=process.versions.node.split(".").map(Number);if(a<22||(a===22&&b<12)){console.error("Node.js 22.12+ required");process.exit(1)}'
if ! "$PYTHON" -c 'import fastapi,uvicorn,pydantic;assert int(pydantic.__version__.split(".")[0])>=2' >/dev/null 2>&1;then
 "$PYTHON" -m pip install -r "$ROOT/backend/requirements.txt"
fi
if [[ ! -f "$ROOT/frontend/node_modules/vite/bin/vite.js" || ! -f "$ROOT/frontend/node_modules/vue/package.json" || ! -f "$ROOT/frontend/node_modules/@vitejs/plugin-vue/package.json" ]];then
 (cd "$ROOT/frontend" && if [[ -f package-lock.json ]];then npm ci --include=dev;else npm install --include=dev;fi)
fi
# Deliberately do not inherit a v1 DB_PATH: the schemas are different.
export DB_PATH="${LIFE_ATLAS_V2_DB_PATH:-$ROOT/backend/var/states-v2.db}"
# exec sends Ctrl+C/SIGTERM/SIGHUP directly to the supervisor.
exec "$PYTHON" "$ROOT/scripts/dev_runner.py" "$@"
