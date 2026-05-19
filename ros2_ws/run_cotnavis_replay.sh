#!/usr/bin/env bash
set -euo pipefail

# Usage: ./ros2_ws/run_cotnavis_replay.sh <bag_path> [loop] [rate] [start_offset] [ros_domain_id]

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <bag_path> [loop_true_or_false] [rate] [start_offset] [ros_domain_id]"
  exit 1
fi

BAG_PATH="$1"
LOOP="${2:-false}"
RATE="${3:-1.0}"
START_OFFSET="${4:-0.0}"
ROS_DOMAIN_ID_VALUE="${5:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROS_DISTRO_VALUE="${ROS_DISTRO:-humble}"

if [[ ! -e "${BAG_PATH}" ]]; then
  echo "Bag path does not exist: ${BAG_PATH}"
  exit 1
fi

source_with_relaxed_nounset() {
  local setup_file="$1"
  local had_nounset=0
  local had_errexit=0
  local status=0

  if [[ ! -f "${setup_file}" ]]; then
    echo "[replay] ERROR: setup file not found: ${setup_file}"
    return 1
  fi

  if [[ $- == *e* ]]; then
    had_errexit=1
    set +e
  fi

  if [[ $- == *u* ]]; then
    had_nounset=1
    set +u
  fi

  source "${setup_file}"
  status=$?

  if [[ "${had_nounset}" -eq 1 ]]; then
    set -u
  fi

  if [[ "${had_errexit}" -eq 1 ]]; then
    set -e
  fi

  if [[ "${status}" -ne 0 ]]; then
    echo "[replay] ERROR: failed to source ${setup_file} (exit ${status})"
    return "${status}"
  fi
}

ensure_python_deps() {
  if python3 - <<'PY' >/dev/null 2>&1
import flask
import flask_socketio
PY
  then
    return
  fi

  echo "[replay] Installing Python runtime dependencies for app.py..."

  if ! python3 -m pip --version >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip
  fi

  python3 -m pip install -r "${REPO_ROOT}/requirements.txt"
  echo "[replay] Python dependencies ready."
}

clear_stale_package_build() {
  local pkg="$1"
  local cache_file="${SCRIPT_DIR}/build/${pkg}/CMakeCache.txt"
  local expected_build_dir="${SCRIPT_DIR}/build/${pkg}"

  [[ -f "${cache_file}" ]] || return 0

  local cached_build_dir
  cached_build_dir="$(sed -n 's|^# For build in directory: ||p' "${cache_file}" | head -n 1 || true)"

  if [[ -n "${cached_build_dir}" && "${cached_build_dir}" != "${expected_build_dir}" ]]; then
    echo "[replay] Detected stale build cache for ${pkg}: ${cached_build_dir}"
    echo "[replay] Clearing stale package build artifacts for ${pkg}..."
    rm -rf "${SCRIPT_DIR}/build/${pkg}" \
           "${SCRIPT_DIR}/install/${pkg}" \
           "${SCRIPT_DIR}/log/latest_build/${pkg}" \
           "${SCRIPT_DIR}/log/latest/${pkg}" || true
  fi
}

echo "[replay] Sourcing ROS: /opt/ros/${ROS_DISTRO_VALUE}/setup.bash"
source_with_relaxed_nounset "/opt/ros/${ROS_DISTRO_VALUE}/setup.bash"
ensure_python_deps

cd "${SCRIPT_DIR}"
clear_stale_package_build amrl_msgs
clear_stale_package_build cotnavis_replay

echo "[replay] Clearing cotnavis_replay generated artifacts..."
rm -rf "${SCRIPT_DIR}/build/cotnavis_replay" "${SCRIPT_DIR}/install/cotnavis_replay" "${SCRIPT_DIR}/log/latest_build/cotnavis_replay" "${SCRIPT_DIR}/log/latest/cotnavis_replay" || true
echo "[replay] Building amrl_msgs..."
colcon build --symlink-install --packages-select amrl_msgs
source_with_relaxed_nounset "${SCRIPT_DIR}/install/setup.bash"
echo "[replay] Building cotnavis_replay..."
colcon build --symlink-install --packages-select cotnavis_replay
source_with_relaxed_nounset "${SCRIPT_DIR}/install/setup.bash"

echo "[replay] Verifying amrl_msgs interface availability..."
if ! ros2 interface show amrl_msgs/msg/ForesightPlannerMsg >/dev/null 2>&1; then
  echo "[replay] ERROR: amrl_msgs/msg/ForesightPlannerMsg not available after sourcing ros2_ws/install/setup.bash"
  echo "[replay] Try manual check: source ${SCRIPT_DIR}/install/setup.bash && ros2 interface show amrl_msgs/msg/ForesightPlannerMsg"
  exit 1
fi

cd "${REPO_ROOT}"
echo "[replay] Starting Flask UI on port 5000..."
python3 app.py &
APP_PID=$!
sleep 1
if ! kill -0 "${APP_PID}" 2>/dev/null; then
  echo "[replay] ERROR: app.py exited immediately."
  wait "${APP_PID}" || true
  exit 1
fi

cleanup() {
  kill "${APP_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID_VALUE}"
BAG_CMD=(ros2 bag play "${BAG_PATH}" --clock --start-offset "${START_OFFSET}" --rate "${RATE}")
if [[ "${LOOP}" == "true" ]]; then
  BAG_CMD+=(--loop)
fi

echo "[replay] Playing bag: ${BAG_PATH}"
echo "[replay] Command: ${BAG_CMD[*]}"
"${BAG_CMD[@]}"
