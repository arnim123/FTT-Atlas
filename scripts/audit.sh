#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
echo "npm audit (frontend)"
(cd "$root/frontend" && npm audit --audit-level=high)
echo "pip check (backend)"
python -m pip check || true
if python -m pip show pip-audit >/dev/null 2>&1; then
  python -m pip_audit -r /dev/null || python -m pip_audit
else
  echo "pip-audit is not installed. Install it with: python -m pip install pip-audit"
fi
