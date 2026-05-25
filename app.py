import base64
import json
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone

try:
    import cv2
except ImportError:
    cv2 = None
from flask import Flask, render_template
from flask_socketio import SocketIO


try:
    import rclpy
    from amrl_msgs.msg import ForesightPlannerMsg
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Path
    from rclpy.node import Node
    from sensor_msgs.msg import CompressedImage, Image, Joy
    from std_msgs.msg import Bool, String
    from visualization_msgs.msg import MarkerArray
except ImportError as exc:
    rclpy = None
    Node = object
    Bool = None
    CompressedImage = None
    ForesightPlannerMsg = None
    Image = None
    Joy = None
    MarkerArray = None
    Path = None
    String = None
    Twist = None
    ROS_IMPORT_ERROR = exc
else:
    ROS_IMPORT_ERROR = None

try:
    from cv_bridge import CvBridge
except ImportError:
    CvBridge = None

GOAL_COMMAND_TOPIC = "/legged_deployment/foresight_planner/goal_command"
FORESIGHT_STATUS_TOPIC = "/legged_deployment/foresight_status"
GRAPH_FORESIGHT_STATUS_TOPIC = "/graph_navigation/foresight_status"
IMAGE_PLAN_TOPIC = "/legged_deployment/image_plan/compressed"
OBSERVATION_MOSAIC_TOPIC = "/legged_deployment/observation_mosaic/compressed"
CAMERA_TOPIC = "/camera/rgb/image_raw/compressed"
AUTONOMY_TOPIC = "/autonomy_arbiter/enabled"
CMD_VEL_TOPIC = "/cmd_vel"
NAV_CMD_VEL_TOPIC = "/navigation/cmd_vel"
JOYSTICK_TOPIC = "/joystick"
TRAJECTORY_TOPIC = "/trajectory"
PATH_ROLLOUTS_TOPIC = "/navigation/path_rollouts"

COMMAND_MATCH_THRESHOLD = 0.05
LOCAL_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "cotnavis_config.json")


app = Flask(__name__)
app.config["SECRET_KEY"] = "ros-replay-dashboard-local"
socketio = SocketIO(app, cors_allowed_origins="*")

state_lock = threading.Lock()
run_context_emit_lock = threading.Lock()
last_run_context_emit_at = 0.0
state = {
    "goal_command": {
        "text": "",
        "topic": GOAL_COMMAND_TOPIC,
        "received_at": None,
    },
    "camera_history": deque(maxlen=4),
    "current_camera": None,
    "foresight_message_count": 0,
    "foresight_queue": [],
    "latest_image_plan": None,
    "latest_observation_mosaic": None,
    "latest_nav_cmd": None,
    "run_context": {
        "autonomy": {
            "topic": AUTONOMY_TOPIC,
            "enabled": None,
            "true_count": 0,
            "false_count": 0,
            "received_at": None,
        },
        "commandComparison": {
            "cmd_topic": CMD_VEL_TOPIC,
            "nav_cmd_topic": NAV_CMD_VEL_TOPIC,
            "cmd_total": 0,
            "nav_cmd_total": 0,
            "match": 0,
            "mismatch": 0,
            "last_diff": None,
            "last_cmd": None,
            "last_nav_cmd": None,
            "last_match": None,
            "received_at": None,
        },
        "joystick": {
            "topic": JOYSTICK_TOPIC,
            "messages": 0,
            "active_messages": 0,
            "axes_count": 0,
            "buttons_count": 0,
            "active_buttons": 0,
            "received_at": None,
        },
        "trajectory": {
            "topic": TRAJECTORY_TOPIC,
            "messages": 0,
            "path_pose_count": 0,
            "first_xy": None,
            "last_xy": None,
            "received_at": None,
        },
        "rollouts": {
            "topic": PATH_ROLLOUTS_TOPIC,
            "messages": 0,
            "marker_count": 0,
            "first_marker_ids": [],
            "received_at": None,
        },
        "graphForesight": {
            "topic": GRAPH_FORESIGHT_STATUS_TOPIC,
            "messages": 0,
            "accepted": 0,
            "rejected": 0,
            "latest_reflection_id": None,
            "latest_reason": "",
            "received_at": None,
        },
    },
}


def received_at():
    return datetime.now(timezone.utc).isoformat()


def parse_ignore_indices(raw_value):
    if raw_value is None:
        return set()

    if isinstance(raw_value, str):
        tokens = raw_value.split(",")
    elif isinstance(raw_value, (list, tuple, set)):
        tokens = list(raw_value)
    else:
        raise ValueError("ignore_foresight_message_indices must be a comma string or a list")

    indices = set()
    for token in tokens:
        if isinstance(token, int):
            index = token
        else:
            token_text = str(token).strip()
            if not token_text:
                continue
            if not token_text.isdigit():
                raise ValueError(f"invalid index value: {token!r}")
            index = int(token_text)
        if index < 1:
            raise ValueError(f"index must be >= 1, got {index}")
        indices.add(index)
    return indices


def load_ignored_foresight_indices():
    if not os.path.exists(LOCAL_CONFIG_PATH):
        return set()

    try:
        with open(LOCAL_CONFIG_PATH, "r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
    except Exception:
        app.logger.exception("Failed to load local config at %s", LOCAL_CONFIG_PATH)
        return set()

    if not isinstance(loaded, dict):
        app.logger.warning("Config file %s must contain a JSON object", LOCAL_CONFIG_PATH)
        return set()

    try:
        ignored = parse_ignore_indices(loaded.get("ignore_foresight_message_indices"))
    except ValueError as exc:
        app.logger.warning("Invalid ignore config in %s: %s", LOCAL_CONFIG_PATH, exc)
        return set()

    if ignored:
        app.logger.info(
            "Ignoring foresight messages by index: %s",
            ", ".join(str(value) for value in sorted(ignored)),
        )
    return ignored


IGNORED_FORESIGHT_MESSAGE_INDICES = load_ignored_foresight_indices()


def snapshot_state():
    with state_lock:
        return {
            "goal_command": dict(state["goal_command"]),
            "camera_history": list(state["camera_history"]),
            "current_camera": dict(state["current_camera"]) if state["current_camera"] else None,
            "foresight_queue": list(state["foresight_queue"]),
            "run_context": {
                key: dict(value) for key, value in state["run_context"].items()
            },
        }


def emit_goal_command():
    socketio.emit("goal_command", snapshot_state()["goal_command"])


def emit_camera_update():
    snapshot = snapshot_state()
    socketio.emit(
        "camera_update",
        {
            "current": snapshot["current_camera"],
            "history": snapshot["camera_history"],
        },
    )


def emit_foresight_trace():
    socketio.emit("foresight_trace", {"queue": snapshot_state()["foresight_queue"]})


def emit_run_context():
    socketio.emit("run_context", snapshot_state()["run_context"])


def emit_run_context_throttled(context, min_interval_seconds=0.1):
    global last_run_context_emit_at

    now = time.monotonic()
    with run_context_emit_lock:
        if now - last_run_context_emit_at < min_interval_seconds:
            return
        last_run_context_emit_at = now

    socketio.emit("run_context", context)


def string_data(value):
    return getattr(value, "data", "") or ""


def bool_data(value):
    data = getattr(value, "data", None)
    return bool(data) if data is not None else None


def extract_fix_text(*texts):
    for text in texts:
        if not text:
            continue
        match = re.search(r"<fix>\s*(.*?)\s*</fix>", text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            cleaned = " ".join(match.group(1).split())
            if cleaned:
                return cleaned

    for text in texts:
        if not text:
            continue
        # Fall back to explicit "fix:" style guidance when XML-like tags are absent.
        match = re.search(r"\bfix\s*:\s*(.+)$", text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        cleaned = " ".join(match.group(1).split())
        if cleaned:
            return cleaned

    return None


def encode_compressed_image(msg):
    if msg is None:
        return None

    try:
        image_format = (getattr(msg, "format", "") or "jpeg").lower()
        mime = "image/png" if "png" in image_format else "image/jpeg"
        encoded = base64.b64encode(bytes(msg.data)).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        app.logger.exception("Failed to encode compressed ROS image")
        return None


def encode_image_message(bridge, msg):
    if bridge is None or cv2 is None:
        return None
    try:
        cv_image = bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        ok, encoded = cv2.imencode(".jpg", cv_image)
        if not ok:
            app.logger.warning("OpenCV failed to encode ROS image as JPEG")
            return None
        jpeg_b64 = base64.b64encode(encoded.tobytes()).decode("ascii")
        return f"data:image/jpeg;base64,{jpeg_b64}"
    except Exception:
        app.logger.exception("Failed to convert ROS image message")
        return None


def set_current_camera_image(image_url, topic, label, timestamp):
    if image_url is None:
        return None, []

    frame = {
        "image": image_url,
        "topic": topic,
        "label": label,
        "received_at": timestamp,
    }
    with state_lock:
        state["current_camera"] = frame
        current = dict(state["current_camera"])
        history = list(state["camera_history"])

    return current, history


def append_observation_history(image_url, topic, label, timestamp):
    if image_url is None:
        return None, []

    frame = {
        "image": image_url,
        "topic": topic,
        "label": label,
        "received_at": timestamp,
    }
    with state_lock:
        state["latest_observation_mosaic"] = frame
        state["camera_history"].clear()
        state["camera_history"].append(frame)
        current = dict(state["current_camera"]) if state["current_camera"] else None
        history = list(state["camera_history"])

    return current, history


def pose_xy(pose_stamped):
    position = pose_stamped.pose.position
    return [round(position.x, 3), round(position.y, 3)]


def twist_vector(msg):
    return [
        round(msg.linear.x, 3),
        round(msg.linear.y, 3),
        round(msg.angular.z, 3),
    ]


def update_command_comparison_for_nav(msg, timestamp):
    nav_cmd = twist_vector(msg)
    with state_lock:
        state["latest_nav_cmd"] = nav_cmd
        comparison = state["run_context"]["commandComparison"]
        comparison["nav_cmd_total"] += 1
        comparison["last_nav_cmd"] = nav_cmd
        comparison["received_at"] = timestamp
        context = {
            key: dict(value) for key, value in state["run_context"].items()
        }
    return context


def update_command_comparison_for_cmd(msg, timestamp):
    cmd = twist_vector(msg)
    with state_lock:
        comparison = state["run_context"]["commandComparison"]
        comparison["cmd_total"] += 1
        comparison["last_cmd"] = cmd
        comparison["received_at"] = timestamp

        nav_cmd = state["latest_nav_cmd"]
        if nav_cmd is not None:
            max_diff = max(abs(cmd_value - nav_value) for cmd_value, nav_value in zip(cmd, nav_cmd))
            matched = max_diff <= COMMAND_MATCH_THRESHOLD
            comparison["last_diff"] = round(max_diff, 3)
            comparison["last_match"] = matched
            if matched:
                comparison["match"] += 1
            else:
                comparison["mismatch"] += 1

        context = {
            key: dict(value) for key, value in state["run_context"].items()
        }
    return context


def select_plan_image(motion_image, image_plan):
    if motion_image:
        return motion_image
    if isinstance(image_plan, dict):
        return image_plan.get("image")
    return None


def normalize_foresight_blocks(msg, topic, timestamp):
    verdict = bool_data(getattr(msg, "verdict", None))
    motion_image = encode_compressed_image(getattr(msg, "motion_image", None))
    path = getattr(msg, "path", None)

    reason = string_data(getattr(msg, "reason", None))
    thinking_text = string_data(getattr(msg, "thinking_text", None))
    motion_text = string_data(getattr(msg, "motion_text", None))
    critic_text = string_data(getattr(msg, "critic_text", None))

    with state_lock:
        image_plan = state["latest_image_plan"]

    plan_image = select_plan_image(motion_image, image_plan)
    base_block = {
        "reflection_id": getattr(msg, "reflection_id", None),
        "verdict": verdict,
        "reason": reason,
        "thinking_text": thinking_text,
        "motion_text": motion_text,
        "critic_text": critic_text,
        "path_pose_count": len(getattr(path, "poses", []) or []),
        "motion_image": plan_image,
        "image_plan": image_plan,
        "topic": topic,
        "received_at": timestamp,
    }

    blocks = [
        {
            **base_block,
            "type": "accepted",
            "status": "ACCEPTED",
            "display_text": "",
        }
    ]

    suggestion = extract_fix_text(reason, critic_text, motion_text, thinking_text)
    if suggestion:
        blocks.append(
            {
                **base_block,
                "type": "fix",
                "status": "FIX",
                "display_text": suggestion,
                "motion_image": None,
            }
        )

    return blocks


class ReplayDashboardNode(Node):
    def __init__(self):
        super().__init__("ros_replay_dashboard")
        self.bridge = CvBridge() if CvBridge is not None else None

        self.create_subscription(String, GOAL_COMMAND_TOPIC, self.on_goal_command, 10)
        self.create_subscription(ForesightPlannerMsg, FORESIGHT_STATUS_TOPIC, self.on_foresight_status, 10)
        self.create_subscription(ForesightPlannerMsg, GRAPH_FORESIGHT_STATUS_TOPIC, self.on_graph_foresight_status, 10)
        self.create_subscription(CompressedImage, IMAGE_PLAN_TOPIC, self.on_image_plan, 10)
        self.create_subscription(CompressedImage, OBSERVATION_MOSAIC_TOPIC, self.on_observation_mosaic, 10)
        self.create_subscription(CompressedImage, CAMERA_TOPIC, self.on_camera_compressed, 10)
        self.create_subscription(Bool, AUTONOMY_TOPIC, self.on_autonomy, 10)
        self.create_subscription(Twist, CMD_VEL_TOPIC, self.on_cmd_vel, 10)
        self.create_subscription(Twist, NAV_CMD_VEL_TOPIC, self.on_nav_cmd_vel, 10)
        self.create_subscription(Joy, JOYSTICK_TOPIC, self.on_joystick, 10)
        self.create_subscription(Path, TRAJECTORY_TOPIC, self.on_trajectory, 10)
        self.create_subscription(MarkerArray, PATH_ROLLOUTS_TOPIC, self.on_path_rollouts, 10)

    def on_goal_command(self, msg):
        timestamp = received_at()
        with state_lock:
            state["goal_command"] = {
                "text": msg.data,
                "topic": GOAL_COMMAND_TOPIC,
                "received_at": timestamp,
            }
        emit_goal_command()

    def on_camera_compressed(self, msg):
        timestamp = received_at()
        current, history = set_current_camera_image(
            encode_compressed_image(msg),
            CAMERA_TOPIC,
            "rgb camera",
            timestamp,
        )
        if current:
            socketio.emit("camera_update", {"current": current, "history": history})

    def on_camera_image(self, msg):
        timestamp = received_at()
        current, history = set_current_camera_image(
            encode_image_message(self.bridge, msg),
            CAMERA_TOPIC,
            "rgb camera",
            timestamp,
        )
        if current:
            socketio.emit("camera_update", {"current": current, "history": history})

    def on_observation_mosaic(self, msg):
        timestamp = received_at()
        current, history = append_observation_history(
            encode_compressed_image(msg),
            OBSERVATION_MOSAIC_TOPIC,
            "observation mosaic",
            timestamp,
        )
        if history:
            socketio.emit("camera_update", {"current": current, "history": history})

    def on_image_plan(self, msg):
        timestamp = received_at()
        image_url = encode_compressed_image(msg)
        if image_url is None:
            return

        with state_lock:
            state["latest_image_plan"] = {
                "image": image_url,
                "topic": IMAGE_PLAN_TOPIC,
                "label": "image plan",
                "received_at": timestamp,
            }

    def on_foresight_status(self, msg):
        with state_lock:
            state["foresight_message_count"] += 1
            message_index = state["foresight_message_count"]

        if message_index in IGNORED_FORESIGHT_MESSAGE_INDICES:
            app.logger.info("Ignoring foresight message #%d from %s", message_index, FORESIGHT_STATUS_TOPIC)
            return

        blocks = normalize_foresight_blocks(msg, FORESIGHT_STATUS_TOPIC, received_at())
        with state_lock:
            accepted_seen = any(block.get("status") == "ACCEPTED" for block in state["foresight_queue"])
            if accepted_seen:
                state["foresight_queue"].clear()
            state["foresight_queue"].extend(blocks)
            queue = list(state["foresight_queue"])
        socketio.emit("foresight_trace", {"queue": queue})

    def on_graph_foresight_status(self, msg):
        timestamp = received_at()
        verdict = bool_data(getattr(msg, "verdict", None))
        with state_lock:
            graph = state["run_context"]["graphForesight"]
            graph["messages"] += 1
            graph["latest_reflection_id"] = getattr(msg, "reflection_id", None)
            graph["latest_reason"] = string_data(getattr(msg, "reason", None))
            graph["received_at"] = timestamp
            if verdict is True:
                graph["accepted"] += 1
            elif verdict is False:
                graph["rejected"] += 1
            context = {
                key: dict(value) for key, value in state["run_context"].items()
            }
        emit_run_context_throttled(context)

    def on_autonomy(self, msg):
        timestamp = received_at()
        enabled = bool(msg.data)
        with state_lock:
            autonomy = state["run_context"]["autonomy"]
            autonomy["enabled"] = enabled
            autonomy["received_at"] = timestamp
            if enabled:
                autonomy["true_count"] += 1
            else:
                autonomy["false_count"] += 1
            context = {
                key: dict(value) for key, value in state["run_context"].items()
            }
        emit_run_context_throttled(context)

    def on_nav_cmd_vel(self, msg):
        emit_run_context_throttled(update_command_comparison_for_nav(msg, received_at()))

    def on_cmd_vel(self, msg):
        emit_run_context_throttled(update_command_comparison_for_cmd(msg, received_at()))

    def on_joystick(self, msg):
        timestamp = received_at()
        active_buttons = sum(1 for button in msg.buttons if button)
        with state_lock:
            joystick = state["run_context"]["joystick"]
            joystick["messages"] += 1
            joystick["axes_count"] = len(msg.axes)
            joystick["buttons_count"] = len(msg.buttons)
            joystick["active_buttons"] = active_buttons
            joystick["received_at"] = timestamp
            if active_buttons:
                joystick["active_messages"] += 1
            context = {
                key: dict(value) for key, value in state["run_context"].items()
            }
        emit_run_context_throttled(context)

    def on_trajectory(self, msg):
        timestamp = received_at()
        poses = list(msg.poses)
        with state_lock:
            trajectory = state["run_context"]["trajectory"]
            trajectory["messages"] += 1
            trajectory["path_pose_count"] = len(poses)
            trajectory["first_xy"] = pose_xy(poses[0]) if poses else None
            trajectory["last_xy"] = pose_xy(poses[-1]) if poses else None
            trajectory["received_at"] = timestamp
            context = {
                key: dict(value) for key, value in state["run_context"].items()
            }
        emit_run_context_throttled(context)

    def on_path_rollouts(self, msg):
        timestamp = received_at()
        markers = list(msg.markers)
        with state_lock:
            rollouts = state["run_context"]["rollouts"]
            rollouts["messages"] += 1
            rollouts["marker_count"] = len(markers)
            rollouts["first_marker_ids"] = [marker.id for marker in markers[:5]]
            rollouts["received_at"] = timestamp
            context = {
                key: dict(value) for key, value in state["run_context"].items()
            }
        emit_run_context_throttled(context)


def run_ros_node():
    if rclpy is None:
        app.logger.warning(
            "ROS2 dependencies are unavailable. Source ROS2 and the AMRL workspace "
            "to receive live replay data. Import error: %s",
            ROS_IMPORT_ERROR,
        )
        return

    rclpy.init()
    node = ReplayDashboardNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def on_connect():
    snapshot = snapshot_state()
    socketio.emit("goal_command", snapshot["goal_command"])
    socketio.emit(
        "camera_update",
        {
            "current": snapshot["current_camera"],
            "history": snapshot["camera_history"],
        },
    )
    socketio.emit("foresight_trace", {"queue": snapshot["foresight_queue"]})
    socketio.emit("run_context", snapshot["run_context"])


if __name__ == "__main__":
    ros_thread = threading.Thread(target=run_ros_node, daemon=True)
    ros_thread.start()
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
