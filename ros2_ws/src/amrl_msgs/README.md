[![ROS1 Noetic](https://github.com/ut-amrl/amrl_msgs/actions/workflows/ros1-noetic.yml/badge.svg)](https://github.com/ut-amrl/amrl_msgs/actions/workflows/ros1-noetic.yml)
[![ROS2 Humble](https://github.com/ut-amrl/amrl_msgs/actions/workflows/ros2-humble.yml/badge.svg)](https://github.com/ut-amrl/amrl_msgs/actions/workflows/ros2-humble.yml)

# AMRL Messages

ROS Message definitions used by UT-AMRL projects.

## Dependencies

[ROS](http://wiki.ros.org/ROS/Installation)

## Usage

1. Clone this repository.
2. **For ROS1**: Add the path to your `~/.bashrc` file for the `ROS_PACKAGE_PATH` environment variable:
    ```bash
    echo "export ROS_PACKAGE_PATH=$(pwd):\$ROS_PACKAGE_PATH" >> ~/.bashrc
    source ~/.bashrc
    ```
3. **For ROS2**: Add the path to your `~/.bashrc` file for the `AMENT_PREFIX_PATH` environment variable:
    ```bash
    echo "export AMENT_PREFIX_PATH=$(pwd)/install:\$AMENT_PREFIX_PATH" >> ~/.bashrc
    source ~/.bashrc
    ```
4. Run `make`. This will automatically build and install (for ROS2) or just build (for ROS1). No need to run `catkin_*`, `rosbuild`, etc.
5. To use the messages from your own project, add `amrl_msgs` as a ROS dependency to your project's `manifest.xml` or `package.xml`.
