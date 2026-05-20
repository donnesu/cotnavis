# COTNAVIS ROS2 Bag Replay (Docker Workflow)

This repo includes a ROS2 workspace at `ros2_ws` with:

- `cotnavis_replay`
- `amrl_msgs` (from `ut-amrl/amrl_msgs`, branch `artzha/foresight`)

## 1) Enter ROS2 Docker shell

From host (`robovision`):

```bash
cd /home/ecocar_robot/PA/Donne/cotnavis
./ros2_ws/docker_shell.sh
```

Default dataset host path mounted into container:

- Host: `/robodata/spot_logs/arthurz/foresight_bags/experiment_logs`
- Container: `/datasets`

## 2) Replay + UI in one command (inside container)

```bash
./ros2_ws/replay.sh /datasets/mission_20260516_004716
```

What this does:

- auto-installs Python runtime deps if missing (`pip`, `flask`, `flask-socketio`, `opencv-python`)
- builds `amrl_msgs` + `cotnavis_replay`
- starts Flask UI (`app.py`) on port `5000`
- replays the bag with `ros2 bag play --clock`

Advanced args:

```bash
./ros2_ws/run_cotnavis_replay.sh <bag_path> [loop] [rate] [start_offset] [ros_domain_id]
```

### Ignore specific foresight messages by receive order

Edit `cotnavis_config.json` at the repo root.

```json
{
  "ignore_foresight_message_indices": "1,2,6"
}
```

This skips the 1st, 2nd, and 6th message received on `/legged_deployment/foresight_status` after `app.py` starts.

## 3) Optional manual split (inside container)

Terminal A:

```bash
cd /home/ecocar_robot/PA/Donne/cotnavis/ros2_ws
source /opt/ros/${ROS_DISTRO}/setup.bash
colcon build --symlink-install --packages-up-to amrl_msgs cotnavis_replay
source install/setup.bash
cd /home/ecocar_robot/PA/Donne/cotnavis
python3 app.py
```

Terminal B:

```bash
cd /home/ecocar_robot/PA/Donne/cotnavis/ros2_ws
source /opt/ros/${ROS_DISTRO}/setup.bash
source install/setup.bash
ros2 bag play /datasets/mission_20260516_004716 --clock
```

## 4) View from local machine

On your laptop:

```bash
./scripts/port_forward_cotnavis.sh robovision <robovision_user> auto 5000
```

Then open the local URL printed by the script (for example `http://127.0.0.1:5000` or `:5001`).
