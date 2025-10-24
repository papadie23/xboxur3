#!/usr/bin/env python3

import socket
import sys
import os

# Add the airo_teleop module to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'airo_teleop'))

def check_robot_connection(ip):
    """Test if robot is reachable and get basic info"""
    print(f"Testing connection to {ip}...")
    
    # Test RTDE port (30004)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        result = sock.connect_ex((ip, 30004))
        sock.close()
        
        if result == 0:
            print(f"✓ RTDE port (30004) is open on {ip}")
            
            # Try to connect with URrtde
            try:
                from airo_robots.manipulators.hardware.ur_rtde import URrtde
                print("Attempting robot connection...")
                robot = URrtde(ip, URrtde.UR3E_CONFIG)
                
                # Test getting pose
                pose = robot.get_tcp_pose()
                print(f"✓ Robot connected successfully!")
                print(f"✓ TCP pose retrieved - Robot is ready")
                return True
                
            except Exception as e:
                print(f"✗ Robot connection failed: {str(e)}")
                print("  Robot may be in protective stop or wrong mode")
                return False
        else:
            print(f"✗ Cannot connect to RTDE port on {ip}")
            return False
            
    except Exception as e:
        print(f"✗ Network error: {str(e)}")
        return False

def scan_network():
    """Scan for UR robots on common networks"""
    print("Scanning for UR robots...")
    networks = ["192.168.0", "192.168.1", "10.42.0"]
    found_robots = []
    
    for network in networks:
        print(f"\nScanning {network}.x...")
        for i in range(1, 255):
            ip = f"{network}.{i}"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                result = sock.connect_ex((ip, 30004))
                sock.close()
                
                if result == 0:
                    print(f"Found potential robot at {ip}")
                    found_robots.append(ip)
                    
            except:
                pass
                
    return found_robots

if __name__ == "__main__":
    print("UR3e Robot Finder")
    print("================")
    
    if len(sys.argv) > 1:
        # Test specific IP
        ip = sys.argv[1]
        check_robot_connection(ip)
    else:
        # Scan network
        robots = scan_network()
        
        if robots:
            print(f"\nFound {len(robots)} potential robot(s):")
            for ip in robots:
                print(f"\nTesting {ip}:")
                check_robot_connection(ip)
        else:
            print("\nNo robots found on network")
            print("\nTo test a specific IP: python find_robot.py <IP_ADDRESS>")
