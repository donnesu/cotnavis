#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <bag_path>"
  echo "Example: $0 /datasets/mission_20260516_004716"
  exit 1
fi

exec bash "${SCRIPT_DIR}/run_cotnavis_replay.sh" "$@"
