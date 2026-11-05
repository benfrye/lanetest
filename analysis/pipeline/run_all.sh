#!/usr/bin/env bash
# Run the full analysis pipeline end to end (METHODOLOGY §3.4: uv-managed Python 3.12 venv at analysis/.venv).
# Usage: analysis/pipeline/run_all.sh            # always exits 0 if every step ran
#        STRICT=1 analysis/pipeline/run_all.sh   # exits 3 if a blocking validation item FAILs
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS="$(dirname "$HERE")"
VENV="$ANALYSIS/.venv"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found: install with 'brew install uv' or 'python3 -m pip install uv'" >&2; exit 1
fi
if [ ! -x "$VENV/bin/python" ]; then
  uv venv --python 3.12 "$VENV"
fi
uv pip install --quiet --python "$VENV/bin/python" -r "$ANALYSIS/requirements.txt"
PY="$VENV/bin/python"
cd "$HERE"
for step in 01_build_dataset 02_labels 03_fit 04_diagnostics 05_errors 06_robustness 07_translation 08_story_data 09_export 10_validate 11_source_story_data; do
  echo "=== $step ==="
  "$PY" -W ignore "$step.py"
done
echo
"$PY" - <<'PYEOF'
import json, pathlib
v = json.load(open(pathlib.Path("../output/validation.json")))
print(f"fit_level = {v['fit_level']}")
for k, it in v["items"].items():
    print(f"  {k:4s} {it['status']:8s} {'blocking' if it['blocking'] else ''}  {it['name']}")
print("blocking FAIL:", v["blocking_fail"] or "none", "| blocking NOT_RUN:", v["blocking_not_run"] or "none")
print("wrote:", v["model_params_written"])
PYEOF
if [ "${STRICT:-0}" = "1" ] && [ -f "$ANALYSIS/output/model_params.BLOCKED.json" ]; then
  echo "STRICT: blocking validation failures" >&2; exit 3
fi
