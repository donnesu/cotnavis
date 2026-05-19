#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${1:-robovision}"
REMOTE_USER="${2:-$USER}"
LOCAL_PORT_INPUT="${3:-5000}"
REMOTE_PORT="${4:-5000}"

is_port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN -n -P >/dev/null 2>&1
    return
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :${port}" | tail -n +2 | grep -q .
    return
  fi
  return 1
}

show_port_owner() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN -n -P || true
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnp "sport = :${port}" || true
  fi
}

next_free_port() {
  local start_port="$1"
  local p
  for ((p=start_port; p<=65535; p++)); do
    if ! is_port_in_use "$p"; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

if [[ "${LOCAL_PORT_INPUT}" == "auto" ]]; then
  LOCAL_PORT="$(next_free_port 5000)"
  if [[ -z "${LOCAL_PORT}" ]]; then
    echo "Could not find a free local port starting at 5000."
    exit 1
  fi
else
  LOCAL_PORT="${LOCAL_PORT_INPUT}"
fi

if is_port_in_use "${LOCAL_PORT}"; then
  echo "Local port ${LOCAL_PORT} is already in use."
  show_port_owner "${LOCAL_PORT}"
  echo
  echo "Use a different local port, e.g.:"
  echo "  $0 ${REMOTE_HOST} ${REMOTE_USER} auto ${REMOTE_PORT}"
  echo "or"
  echo "  $0 ${REMOTE_HOST} ${REMOTE_USER} 5001 ${REMOTE_PORT}"
  exit 1
fi

cat <<MSG
Starting SSH tunnel:
  local  http://127.0.0.1:${LOCAL_PORT}
  remote ${REMOTE_HOST}:127.0.0.1:${REMOTE_PORT}
Press Ctrl+C to stop forwarding.
MSG

exec ssh -N \
  -L "${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" \
  "${REMOTE_USER}@${REMOTE_HOST}"
