"""
SUMO utility functions for traffic simulation setup and configuration.
"""

import os
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional


def generate_network_xml(network_config: Dict) -> str:
    """
    Generate SUMO network XML configuration for 3-intersection system.

    Args:
        network_config: Dictionary containing network parameters

    Returns:
        Path to generated network file
    """
    net = ET.Element('net')
    net.set('version', '1.9')
    net.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    net.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/net_file.xsd')

    # Define 3 intersections
    intersections = [
        {'id': 'intersection_1', 'x': '0.0', 'y': '0.0', 'type': 'traffic_light'},
        {'id': 'intersection_2', 'x': '0.0', 'y': '200.0', 'type': 'traffic_light'},
        {'id': 'intersection_3', 'x': '200.0', 'y': '0.0', 'type': 'traffic_light'}
    ]

    # Create intersections
    for inter in intersections:
        junction = ET.SubElement(net, 'junction')
        junction.set('id', inter['id'])
        junction.set('type', inter['type'])
        junction.set('x', inter['x'])
        junction.set('y', inter['y'])
        junction.set('z', '0.0')

    # Define traffic light logic for each intersection
    for inter_id in ['intersection_1', 'intersection_2', 'intersection_3']:
        tl_logic = ET.SubElement(net, 'tlLogic')
        tl_logic.set('id', inter_id)
        tl_logic.set('type', 'static')
        tl_logic.set('programID', '0')
        tl_logic.set('offset', '0')

        # Define phases: N-S green, E-W green, all red (offset by intersection)
        offset = 0 if inter_id == 'intersection_1' else 15
        phases = [
            {'duration': '31', 'state': 'GGrrGGrr'},  # N-S green
            {'duration': '3', 'state': 'yyryyryr'},   # Yellow transition
            {'duration': '31', 'state': 'rrGGrrGG'},  # E-W green
            {'duration': '3', 'state': 'rryyrryr'}    # Yellow transition
        ]

        for i, phase in enumerate(phases):
            phase_elem = ET.SubElement(tl_logic, 'phase')
            phase_elem.set('duration', phase['duration'])
            phase_elem.set('state', phase['state'])

    # Write to file
    tree = ET.ElementTree(net)
    net_file = 'network.net.xml'
    tree.write(net_file)

    return net_file


def generate_routes_xml(route_config: Dict) -> str:
    """
    Generate SUMO routes XML configuration with multiple vehicle types and complex routes.

    Args:
        route_config: Dictionary containing route parameters

    Returns:
        Path to generated routes file
    """
    routes = ET.Element('routes')
    routes.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    routes.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/routes_file.xsd')

    # Define multiple vehicle types
    vehicle_types = [
        # Xe máy (motorcycle) - nhanh, nhỏ
        {'id': 'motorcycle', 'accel': '3.0', 'decel': '5.0', 'sigma': '0.3', 'length': '2.0', 'maxSpeed': '60.0'},
        # Xe ô tô (car) - trung bình
        {'id': 'car', 'accel': '2.6', 'decel': '4.5', 'sigma': '0.5', 'length': '5.0', 'maxSpeed': '70.0'},
        # Container (truck) - chậm, lớn
        {'id': 'truck', 'accel': '1.5', 'decel': '3.0', 'sigma': '0.8', 'length': '12.0', 'maxSpeed': '50.0'},
        # Xe 3 bánh (3-wheeler) - nhỏ, linh hoạt
        {'id': 'three_wheeler', 'accel': '2.0', 'decel': '4.0', 'sigma': '0.4', 'length': '3.0', 'maxSpeed': '45.0'}
    ]

    # Create vehicle types
    for vtype_data in vehicle_types:
        vtype = ET.SubElement(routes, 'vType')
        for key, value in vtype_data.items():
            vtype.set(key, str(value))

    # Define complex routes between 3 intersections
    route_definitions = [
        # Routes through intersection 1 (main)
        {'id': 'north_south_main', 'edges': 'north_1 south_1'},
        {'id': 'south_north_main', 'edges': 'south_1 north_1'},
        {'id': 'east_west_main', 'edges': 'east_1 west_1'},
        {'id': 'west_east_main', 'edges': 'west_1 east_1'},

        # Routes to/from intersection 2 (north)
        {'id': 'north_south_north', 'edges': 'north_2 south_2'},
        {'id': 'south_north_north', 'edges': 'south_2 north_2'},
        {'id': 'connect_1_to_2', 'edges': 'south_1 north_2'},
        {'id': 'connect_2_to_1', 'edges': 'south_2 north_1'},

        # Routes to/from intersection 3 (east)
        {'id': 'east_west_east', 'edges': 'east_3 west_3'},
        {'id': 'west_east_east', 'edges': 'west_3 east_3'},
        {'id': 'connect_1_to_3', 'edges': 'east_1 west_3'},
        {'id': 'connect_3_to_1', 'edges': 'east_3 west_1'}
    ]

    # Create routes
    for route_data in route_definitions:
        route = ET.SubElement(routes, 'route')
        route.set('id', route_data['id'])
        route.set('edges', route_data['edges'])

    # Write to file
    tree = ET.ElementTree(routes)
    rou_file = 'routes.rou.xml'
    tree.write(rou_file)

    return rou_file


def generate_sumocfg(sumo_config: Dict) -> str:
    """
    Generate SUMO configuration file for 3-intersection system.

    Args:
        sumo_config: Dictionary containing SUMO parameters

    Returns:
        Path to generated config file
    """
    config = ET.Element('configuration')
    config.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    config.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/sumoConfiguration.xsd')

    # Input files
    input_elem = ET.SubElement(config, 'input')
    net_file_elem = ET.SubElement(input_elem, 'net-file')
    net_file_elem.set('value', 'network.net.xml')
    route_file_elem = ET.SubElement(input_elem, 'route-files')
    route_file_elem.set('value', 'routes.rou.xml')

    # Time settings
    time_elem = ET.SubElement(config, 'time')
    begin_elem = ET.SubElement(time_elem, 'begin')
    begin_elem.set('value', '0')
    end_elem = ET.SubElement(time_elem, 'end')
    end_elem.set('value', str(sumo_config.get('end_time', 3600)))

    # Processing options for complex network
    processing_elem = ET.SubElement(config, 'processing')
    ignore_elem = ET.SubElement(processing_elem, 'ignore-route-errors')
    ignore_elem.set('value', 'true')

    # Add lateral resolution for better simulation
    lateral_elem = ET.SubElement(processing_elem, 'lateral-resolution')
    lateral_elem.set('value', '0.8')

    # Write to file
    tree = ET.ElementTree(config)
    cfg_file = 'simulation.sumocfg'
    tree.write(cfg_file)

    return cfg_file


def start_sumo_gui(cfg_file: str) -> Optional[subprocess.Popen]:
    """
    Start SUMO GUI in background.

    Args:
        cfg_file: Path to SUMO configuration file

    Returns:
        Process handle if successful, None otherwise
    """
    try:
        process = subprocess.Popen(['sumo-gui', '-c', cfg_file],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        return process
    except FileNotFoundError:
        print("SUMO GUI not found. Make sure SUMO is installed and in PATH.")
        return None


def start_sumo(cfg_file: str) -> Optional[subprocess.Popen]:
    """
    Start SUMO in background.

    Args:
        cfg_file: Path to SUMO configuration file

    Returns:
        Process handle if successful, None otherwise
    """
    if not check_sumo_installation():
        return create_mock_sumo_process()

    try:
        process = subprocess.Popen(['sumo', '-c', cfg_file],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        return process
    except FileNotFoundError:
        print("SUMO not found. Make sure SUMO is installed and in PATH.")
        return None


def check_sumo_installation() -> bool:
    """
    Check if SUMO is properly installed.

    Returns:
        True if SUMO is available, False otherwise
    """
    try:
        subprocess.run(['sumo', '--version'],
                      stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL,
                      check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("SUMO not found. For installation instructions, see:")
        print("https://sumo.dlr.de/docs/Installing/index.html")
        return False


def create_mock_sumo_process():
    """
    Create a mock SUMO process for testing when SUMO is not installed.
    This allows the code to run without SUMO for development purposes.
    """
    print("WARNING: Using mock SUMO process - no actual simulation will run!")
    return None
