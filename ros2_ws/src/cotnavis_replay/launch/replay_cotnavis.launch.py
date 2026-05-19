from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    bag_path = LaunchConfiguration("bag_path")
    cotnavis_root = LaunchConfiguration("cotnavis_root")
    loop = LaunchConfiguration("loop")
    rate = LaunchConfiguration("rate")
    start_offset = LaunchConfiguration("start_offset")
    ros_domain_id = LaunchConfiguration("ros_domain_id")

    launch_visualizer = ExecuteProcess(
        cmd=[
            "bash",
            "-lc",
            ["cd ", cotnavis_root, " && python3 app.py"],
        ],
        output="screen",
        additional_env={"ROS_DOMAIN_ID": ros_domain_id},
    )

    bag_play_no_loop = ExecuteProcess(
        cmd=[
            "ros2",
            "bag",
            "play",
            bag_path,
            "--clock",
            "--start-offset",
            start_offset,
            "--rate",
            rate,
        ],
        condition=UnlessCondition(loop),
        output="screen",
        additional_env={"ROS_DOMAIN_ID": ros_domain_id},
    )

    bag_play_loop = ExecuteProcess(
        cmd=[
            "ros2",
            "bag",
            "play",
            bag_path,
            "--clock",
            "--start-offset",
            start_offset,
            "--rate",
            rate,
            "--loop",
        ],
        condition=IfCondition(loop),
        output="screen",
        additional_env={"ROS_DOMAIN_ID": ros_domain_id},
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "bag_path",
                description="Absolute path to rosbag2 directory to replay.",
            ),
            DeclareLaunchArgument(
                "cotnavis_root",
                default_value=".",
                description="Path to the cotnavis repo root containing app.py.",
            ),
            DeclareLaunchArgument(
                "loop",
                default_value="false",
                description="Whether to loop ros2 bag replay.",
            ),
            DeclareLaunchArgument(
                "rate",
                default_value="1.0",
                description="Playback rate multiplier for ros2 bag play.",
            ),
            DeclareLaunchArgument(
                "start_offset",
                default_value="0.0",
                description="Seconds from beginning of bag before playback starts.",
            ),
            DeclareLaunchArgument(
                "ros_domain_id",
                default_value="0",
                description="ROS domain id shared by visualization and replay.",
            ),
            launch_visualizer,
            bag_play_no_loop,
            bag_play_loop,
        ]
    )
