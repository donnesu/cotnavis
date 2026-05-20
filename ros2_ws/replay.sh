#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <bag_path>"
  echo "Example: $0 /datasets/mission_20260516_004716"
  exit 1
fi

# Prevent conflicts with stale services bound to port 5000.
if command -v lsof >/dev/null 2>&1; then
  mapfile -t pids < <(lsof -ti tcp:5000 || true)
elif command -v fuser >/dev/null 2>&1; then
  mapfile -t pids < <(fuser -n tcp 5000 2>/dev/null | tr ' ' '\n' || true)
else
  pids=()
fi

if [[ ${#pids[@]} -gt 0 ]]; then
  echo "Stopping process(es) on port 5000: ${pids[*]}"
  kill "${pids[@]}" 2>/dev/null || true
fi

exec bash "${SCRIPT_DIR}/run_cotnavis_replay.sh" "$@"
