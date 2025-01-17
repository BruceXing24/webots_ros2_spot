import os
import pathlib
import launch
from launch import LaunchDescription
from launch.substitutions.path_join_substitution import PathJoinSubstitution
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.substitutions import LaunchConfiguration
from webots_ros2_driver.webots_launcher import WebotsLauncher, Ros2SupervisorLauncher
from webots_ros2_driver.utils import controller_url_prefix
import random

alphabets = 'ABCDEFGHIJ'
tag_locations = \
[
    ['-1.25 9.2 0.5', '0 0 1 0'],
    ['0.6 10.85 0.5', '0 0 1 -1.57'],
    ['5.0 10.85 0.5', '0 0 1 -1.57'],
    ['6.95 8.7 0.5', '0 0 1 0'],
    ['10.85 7.7 0.5', '0 0 1 0'],
    ['9.0 6.13 0.5', '0 0 1 -1.57'],
    ['9.4 -1.97 0.5', '0 0 1 -1.57'],
    ['7.78 0.0 0.5', '0 0 1 0'],
    ['6.5 -1.97 0.5', '0 0 1 -1.57'],
    ['1.26 0.8 0.5', '0 0 1 0']
]

package_dir = get_package_share_directory('webots_spot')


def get_ros2_nodes(*args):
    spot_driver = Node(
        package='webots_ros2_driver',
        executable='driver',
        output='screen',
        additional_env={'WEBOTS_CONTROLLER_URL': controller_url_prefix() + 'Spot'},
        parameters=[
            {'robot_description': pathlib.Path(os.path.join(package_dir, 'resource', 'spot.urdf')).read_text()},
            {'use_sim_time': False},
            {'set_robot_state_publisher': False}, # foot positions are wrong with webot's urdf
        ],
    )
    return [
        spot_driver,
    ]


def generate_launch_description():
    world = os.path.join(package_dir, 'worlds', 'spot.wbt')
    with open(world, 'r') as f:
        world_txt = f.read()

    modified_world = os.path.join(package_dir, 'worlds', 'modified_spot.wbt')
    with open(modified_world, 'w') as f:
        tags = random.sample(range(1, 20), 5)
        locations = random.sample(range(0, 10), 5)
        externproto_txt = ''
        pairs = ''
        for t, l in zip(tags, locations):
            tag_id = 'tag36_11_' + str(t).zfill(5)

            externproto_txt = externproto_txt + 'EXTERNPROTO "../protos/apriltags/protos/' + tag_id + '.proto"\n'

            apriltag = tag_id + ' {\n'
            apriltag = apriltag + '  translation ' + tag_locations[l][0] + '\n'
            apriltag = apriltag + '  rotation ' + tag_locations[l][1] + '\n}\n'

            pairs = pairs + alphabets[l] + ':' + str(t) + '\n'

            world_txt = world_txt + apriltag

        world_txt = world_txt.split('\n')
        world_txt[1] = externproto_txt
        world_txt = '\n'.join(world_txt)

        f.write(world_txt)

    with open('pairs.txt', 'w') as f:
        f.write(pairs)

    webots = WebotsLauncher(
        world=PathJoinSubstitution([package_dir, 'worlds', 'modified_spot.wbt'])
    )

    apriltag = LaunchConfiguration('detect_tags', default=False)
    spot_apriltag = Node(
        package='webots_spot',
        executable='apriltag_ros',
        output='screen',
        condition=launch.conditions.IfCondition(apriltag),
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[
            {'robot_description': pathlib.Path(os.path.join(package_dir, 'resource', 'rd_spot.urdf')).read_text()},
            {'use_sim_time': False},
        ],
    )

    ros2_supervisor = Ros2SupervisorLauncher()

    # The following line is important!
    # This event handler respawns the ROS 2 nodes on simulation reset (supervisor process ends).
    reset_handler = launch.actions.RegisterEventHandler(
        event_handler=launch.event_handlers.OnProcessExit(
            target_action=ros2_supervisor,
            on_exit=get_ros2_nodes,
        )
    )

    webots_event_handler = launch.actions.RegisterEventHandler(
        event_handler=launch.event_handlers.OnProcessExit(
            target_action=webots,
            on_exit=[
                launch.actions.UnregisterEventHandler(
                    event_handler=reset_handler.event_handler
                ),
                launch.actions.EmitEvent(event=launch.events.Shutdown())
            ],
        )
    )

    return LaunchDescription([
        webots,
        ros2_supervisor,
        robot_state_publisher,
        spot_apriltag,
        webots_event_handler,
        reset_handler,
        Node(
            package='pointcloud_to_laserscan', executable='pointcloud_to_laserscan_node',
            remappings=[('cloud_in', '/Spot/Velodyne_Puck/point_cloud'), ],
            parameters=[{
                'transform_tolerance': 0.01,
                'min_height': 0.0,
                'max_height': 1.0,
                'angle_min': -3.14,
                'angle_max': 3.14,
                'angle_increment': 0.00872,
                'scan_time': 0.1,
                'range_min': 0.45,
                'range_max': 100.0,
                'use_inf': True,
                'inf_epsilon': 1.0,
            }],
            name='pointcloud_to_laserscan'
        ),
    ] + get_ros2_nodes())
