#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DATASET_HOST_ROOT_DEFAULT="/robodata/spot_logs/arthurz/foresight_bags/experiment_logs"
DATASET_HOST_ROOT="${1:-${DATASET_HOST_ROOT_DEFAULT}}"
ROS_DISTRO_VALUE="${ROS_DISTRO:-humble}"
ROS_DOCKER_IMAGE="${ROS_DOCKER_IMAGE:-osrf/ros:${ROS_DISTRO_VALUE}-desktop}"
CONTAINER_NAME="${CONTAINER_NAME:-cotnavis-shell}"

if [[ ! -d "${DATASET_HOST_ROOT}" ]]; then
  echo "Dataset root does not exist: ${DATASET_HOST_ROOT}"
  echo "Usage: $0 [dataset_host_root]"
  exit 1
fi

echo "Launching ROS2 shell container"
echo "Image: ${ROS_DOCKER_IMAGE}"
echo "Repo mount: ${REPO_ROOT}"
echo "Dataset mount: ${DATASET_HOST_ROOT} -> /datasets"

docker run --rm -it \
  --name "${CONTAINER_NAME}" \
  --network host \
  -e ROS_DISTRO="${ROS_DISTRO_VALUE}" \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}" \
  -v "${REPO_ROOT}:${REPO_ROOT}" \
  -v "${DATASET_HOST_ROOT}:/datasets:ro" \
  -w "${REPO_ROOT}" \
  "${ROS_DOCKER_IMAGE}" \
  /bin/bash -lc "source /opt/ros/${ROS_DISTRO_VALUE}/setup.bash && echo 'Container ready. Bags are under /datasets.' && exec bash"
