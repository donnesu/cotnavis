PROJECT(amrl_msgs)
CMAKE_MINIMUM_REQUIRED(VERSION 3.8)

if(DEFINED ENV{ROS_VERSION})
  set(ROS_VERSION $ENV{ROS_VERSION})
else()
  message(FATAL_ERROR "ROS_VERSION is not defined")
endif()

if(${ROS_VERSION} EQUAL "1")
  message(STATUS "Compiling with ROS1 ROSBUILD")
  INCLUDE($ENV{ROS_ROOT}/core/rosbuild/rosbuild.cmake)
  ROSBUILD_INIT()
  SET(ROS_BUILD_STATIC_LIBS true)
  SET(ROS_BUILD_SHARED_LIBS false)

  # Set the directory for message and service files
  FILE(GLOB_RECURSE MSG_FILES msg/*.msg)
  FILE(GLOB_RECURSE SRV_FILES srv/*.srv)

  ROSBUILD_GENMSG()
  ROSBUILD_GENSRV()
elseif(${ROS_VERSION} EQUAL "2")
  message(STATUS "Compiling with ROS2 COLCON")
  add_compile_definitions(ROS2)
  find_package(ament_cmake REQUIRED)
  find_package(geometry_msgs REQUIRED)
  find_package(sensor_msgs REQUIRED)
  find_package(nav_msgs REQUIRED)
  find_package(std_msgs REQUIRED)
  find_package(rosidl_default_generators REQUIRED)

  rosidl_generate_interfaces(${PROJECT_NAME}
    "msg/AckermannCurvatureDriveMsg.msg"
    "msg/BBox2DArrayMsg.msg"
    "msg/BBox2DMsg.msg"
    "msg/ColoredArc2D.msg"
    "msg/ColoredLine2D.msg"
    "msg/ColoredPoint2D.msg"
    "msg/ColoredText.msg"
    "msg/ElevatorCommand.msg"
    "msg/ElevatorStatus.msg"
    "msg/ErrorReport.msg"
    "msg/ForesightPlannerMsg.msg"
    "msg/GPSArrayMsg.msg"
    "msg/GPSMsg.msg"
    "msg/HumanStateArrayMsg.msg"
    "msg/HumanStateMsg.msg"
    "msg/Localization2DMsg.msg"
    "msg/MissionStatusMsg.msg"
    "msg/NavStatusMsg.msg"
    "msg/PathVisualization.msg"
    "msg/PlanarObjDetection.msg"
    "msg/Point2D.msg"
    "msg/Pose2Df.msg"
    "msg/RobofleetStatus.msg"
    "msg/RobofleetSubscription.msg"
    "msg/TurtlebotDockStatus.msg"
    "msg/VisualizationMsg.msg"
    "srv/CarrotPlannerSrv.srv"
    "srv/ForesightPlannerSrv.srv"
    "srv/CostmapSrv.srv"
    "srv/GraphNavGPSSrv.srv"
    "srv/ObjectDetectionSrv.srv"
    "srv/SocialPipsSrv.srv"
    "srv/TwistExecutedSrv.srv"
    "srv/RecoveryDetectSrv.srv"
    "action/TurtlebotDock.action"
    "action/RecoveryExecute.action"
    DEPENDENCIES sensor_msgs geometry_msgs nav_msgs std_msgs 
  )

  # --- Add install steps ---
  # If you have headers in an include directory, install them:
  if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/include")
    install(
      DIRECTORY include/
      DESTINATION include
    )
  endif()

  # Install the generated libraries
  install(
    DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/rosidl_typesupport_fastrtps_cpp/" 
    DESTINATION lib
    FILES_MATCHING PATTERN "*.so"
  )


  # Install the generated interface files and any message, srv, or action files.
  install(
    DIRECTORY msg srv action
    DESTINATION share/${PROJECT_NAME}
  )

  # Export runtime dependencies
  ament_export_dependencies(rosidl_default_runtime)

  ament_package()
else()
  message(FATAL_ERROR "Unknown ROS_VERSION ${ROS_VERSION}")
endif()
