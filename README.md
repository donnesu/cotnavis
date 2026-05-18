# ROS2 Replay Dashboard

Local Flask + ROS2 replay visualization dashboard for ROS2 bag output.

## Install dependencies

```bash
cd ros_replay_dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`cv_bridge`, `rclpy`, `sensor_msgs`, and `std_msgs` usually come from ROS packages instead of pip:

```bash
sudo apt install ros-${ROS_DISTRO}-cv-bridge
```

## Source ROS2

Source your ROS2 environment before running the dashboard:

```bash
source /opt/ros/${ROS_DISTRO}/setup.bash
```

If you use a workspace overlay, source it after ROS2:

```bash
source ~/ros2_ws/install/setup.bash
```

## Run the Flask app

```bash
python app.py
```

If your system only exposes Python 3 as `python3`, use:

```bash
python3 app.py
```

Open:

```text
http://localhost:5000
```

The page loads even if no ROS messages have arrived.

## Play the mission bag

In another terminal with ROS2 and your AMRL workspace sourced:

```bash
ros2 bag play /bags/mission_20260515_152755 --clock
```

The dashboard is a live subscriber view. It does not read bag files directly; keep the
Flask app running while `ros2 bag play` publishes the recorded topics.

## Expected topics

Primary research/reasoning streams:

- `/legged_deployment/foresight_planner/goal_command`: `std_msgs/msg/String`
- `/legged_deployment/foresight_status`: `amrl_msgs/msg/ForesightPlannerMsg`
- `/graph_navigation/foresight_status`: `amrl_msgs/msg/ForesightPlannerMsg`
- `/legged_deployment/image_plan/compressed`: `sensor_msgs/msg/CompressedImage`
- `/legged_deployment/observation_mosaic/compressed`: `sensor_msgs/msg/CompressedImage`
- `/camera/rgb/image_raw/compressed`: `sensor_msgs/msg/CompressedImage`

Execution/context streams:

- `/autonomy_arbiter/enabled`: `std_msgs/msg/Bool`
- `/cmd_vel`: `geometry_msgs/msg/Twist`
- `/navigation/cmd_vel`: `geometry_msgs/msg/Twist`
- `/joystick`: `sensor_msgs/msg/Joy`
- `/trajectory`: `nav_msgs/msg/Path`
- `/navigation/path_rollouts`: `visualization_msgs/msg/MarkerArray`

The main planner queue is driven by `/legged_deployment/foresight_status`. Graph
navigation foresight is summarized as secondary context.
