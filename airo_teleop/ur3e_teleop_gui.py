#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox
import pygame
import threading
import time
import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from airo_robots.manipulators.hardware.ur_rtde import URrtde
from airo_robots.grippers import Robotiq2F85
from airo_teleop.game_controller_mapping import XBox360Layout
from airo_teleop.game_controller_teleop import GameControllerTeleop


class UR3eTeleopGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("UR3e Teleop Controller")
        self.root.geometry("600x500")
        
        # State variables
        self.robot: Optional[URrtde] = None
        self.teleop: Optional[GameControllerTeleop] = None
        self.controller_connected = False
        self.is_recording = False
        self.recording_data: List[Dict[str, Any]] = []
        self.control_thread: Optional[threading.Thread] = None
        self.running = False
        self.scanning = False
        
        self.setup_ui()
        self.check_controller()
        
    def scan_for_robots(self):
        """Scan local network for UR robots"""
        print("Starting network scan for UR robots...")
        self.log_status("Scanning for UR robots...")
        self.scan_btn.config(state="disabled", text="Scanning...")
        
        def scan_thread():
            robots = []
            try:
                # Get local network ranges to scan
                networks = ["192.168.0", "192.168.1", "10.42.0"]
                
                for network in networks:
                    if not self.scanning:
                        break
                    print(f"Scanning network {network}.x...")
                    self.log_status(f"Scanning {network}.x...")
                    
                    for i in range(1, 255):
                        if not self.scanning:
                            break
                        ip = f"{network}.{i}"
                        if self.check_ur_robot(ip):
                            robots.append(ip)
                            print(f"Found UR robot at {ip}")
                            
            except Exception as e:
                print(f"Scan error: {str(e)}")
                self.log_status(f"Scan error: {str(e)}")
                
            self.root.after(0, lambda: self.scan_complete(robots))
            
        self.scanning = True
        threading.Thread(target=scan_thread, daemon=True).start()
        
    def check_ur_robot(self, ip: str) -> bool:
        """Check if IP has a UR robot"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            result = sock.connect_ex((ip, 30004))  # UR RTDE port
            sock.close()
            if result == 0:
                print(f"UR robot detected at {ip}")
                return True
            return False
        except:
            return False
            
    def scan_complete(self, robots: List[str]):
        """Handle scan completion"""
        self.scanning = False
        self.scan_btn.config(state="normal", text="Scan Network")
        
        if robots:
            self.robot_combo['values'] = robots
            self.robot_combo.set(robots[0])
            self.log_status(f"Found {len(robots)} robot(s): {', '.join(robots)}")
        else:
            self.log_status("No robots found on network")
            
    def stop_scan(self):
        """Stop network scan"""
        self.scanning = False
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Robot connection section
        conn_frame = ttk.LabelFrame(main_frame, text="Robot Connection", padding="10")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(conn_frame, text="Robot IP:").grid(row=0, column=0, sticky=tk.W)
        self.robot_combo = ttk.Combobox(conn_frame, width=18)
        self.robot_combo.grid(row=0, column=1, padx=5)
        
        self.scan_btn = ttk.Button(conn_frame, text="Scan Network", command=self.scan_for_robots)
        self.scan_btn.grid(row=0, column=2, padx=2)
        
        self.connect_btn = ttk.Button(conn_frame, text="Connect Robot", command=self.connect_robot)
        self.connect_btn.grid(row=0, column=3, padx=2)
        
        self.robot_status = ttk.Label(conn_frame, text="Not Connected", foreground="red")
        self.robot_status.grid(row=1, column=0, columnspan=4, pady=5)
        
        # Controller section
        ctrl_frame = ttk.LabelFrame(main_frame, text="Xbox Controller", padding="10")
        ctrl_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.controller_status = ttk.Label(ctrl_frame, text="Checking...", foreground="orange")
        self.controller_status.grid(row=0, column=0, pady=5)
        
        ttk.Button(ctrl_frame, text="Refresh Controller", command=self.check_controller).grid(row=1, column=0, pady=5)
        
        # Speed control section
        speed_frame = ttk.LabelFrame(main_frame, text="Speed Control", padding="10")
        speed_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(speed_frame, text="Speed:").grid(row=0, column=0, sticky=tk.W)
        self.speed_var = tk.DoubleVar(value=20.0)
        self.speed_scale = ttk.Scale(speed_frame, from_=1.0, to=100.0, variable=self.speed_var, orient=tk.HORIZONTAL)
        self.speed_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        self.speed_label = ttk.Label(speed_frame, text="20%")
        self.speed_label.grid(row=0, column=2)
        
        self.speed_var.trace('w', self.update_speed_label)
        
        # Control section
        control_frame = ttk.LabelFrame(main_frame, text="Robot Control", padding="10")
        control_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.start_btn = ttk.Button(control_frame, text="Start Control", command=self.start_control, state="disabled")
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop Control", command=self.stop_control, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=5)
        
        # Recording section
        record_frame = ttk.LabelFrame(main_frame, text="Recording", padding="10")
        record_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.record_btn = ttk.Button(record_frame, text="Start Recording", command=self.toggle_recording, state="disabled")
        self.record_btn.grid(row=0, column=0, padx=5)
        
        self.save_btn = ttk.Button(record_frame, text="Save Recording", command=self.save_recording, state="disabled")
        self.save_btn.grid(row=0, column=1, padx=5)
        
        self.record_status = ttk.Label(record_frame, text="Not Recording")
        self.record_status.grid(row=1, column=0, columnspan=2, pady=5)
        
        # Status section
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.status_text = tk.Text(status_frame, height=8, width=70)
        scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=scrollbar.set)
        
        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        status_frame.columnconfigure(0, weight=1)
        
    def log_status(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.root.update_idletasks()
        
    def check_controller(self):
        try:
            pygame.init()
            pygame.joystick.init()
            
            if pygame.joystick.get_count() > 0:
                controller = pygame.joystick.Joystick(0)
                controller_name = controller.get_name()
                self.controller_connected = True
                self.controller_status.config(text=f"Connected: {controller_name}", foreground="green")
                self.log_status(f"Controller detected: {controller_name}")
            else:
                self.controller_connected = False
                self.controller_status.config(text="No Controller Detected", foreground="red")
                self.log_status("No controller detected")
                
        except Exception as e:
            self.controller_connected = False
            self.controller_status.config(text="Controller Error", foreground="red")
            self.log_status(f"Controller error: {str(e)}")
            
    def connect_robot(self):
        try:
            ip = self.robot_combo.get().strip()
            if not ip:
                messagebox.showerror("Error", "Please select or enter robot IP address")
                return
                
            print(f"Attempting to connect to UR3e at {ip}...")
            self.log_status(f"Connecting to robot at {ip}...")
            
            # Test basic connectivity first
            print("Testing network connectivity...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            result = sock.connect_ex((ip, 30004))
            sock.close()
            
            if result != 0:
                error_msg = f"Cannot reach robot at {ip}:30004. Check IP and network connection."
                print(f"Connection failed: {error_msg}")
                messagebox.showerror("Connection Error", error_msg)
                return
                
            print("Network connectivity OK, initializing robot...")
            self.log_status("Network OK, initializing robot...")
            
            # Create robot connection with timeout handling
            self.robot = URrtde(ip, URrtde.UR3E_CONFIG)
            
            print("Robot connected, checking state...")
            self.log_status("Robot connected, checking state...")
            
            # Check robot state
            try:
                pose = self.robot.get_tcp_pose()
                print("Robot state: OK - Ready for control")
                self.log_status("Robot state: Ready for control")
            except Exception as e:
                print(f"Robot state error: {str(e)}")
                self.log_status(f"Robot state error: {str(e)}")
                messagebox.showwarning("Robot State", 
                    "Robot connected but may not be ready. Ensure robot is:\n"
                    "- Powered on\n"
                    "- Not in protective stop\n"
                    "- Program is running or robot is in remote control mode")
            
            # Try to connect gripper
            print("Attempting gripper connection...")
            try:
                gripper = Robotiq2F85(ip)
                self.robot.gripper = gripper
                print("Gripper connected successfully")
                self.log_status("Gripper connected")
            except Exception as e:
                print(f"Gripper connection failed: {str(e)}")
                self.log_status(f"Gripper connection failed: {str(e)}")
                
            self.robot_status.config(text=f"Connected to {ip}", foreground="green")
            self.connect_btn.config(text="Disconnect", command=self.disconnect_robot)
            self.update_button_states()
            print("Robot connection completed successfully")
            self.log_status("Robot connected successfully")
            
        except Exception as e:
            error_msg = f"Failed to connect to robot: {str(e)}"
            print(f"Connection error: {error_msg}")
            messagebox.showerror("Connection Error", error_msg)
            self.log_status(f"Robot connection failed: {str(e)}")
            
    def disconnect_robot(self):
        if self.running:
            self.stop_control()
            
        self.robot = None
        self.robot_status.config(text="Not Connected", foreground="red")
        self.connect_btn.config(text="Connect Robot", command=self.connect_robot)
        self.update_button_states()
        self.log_status("Robot disconnected")
        
    def update_speed_label(self, *args):
        speed = self.speed_var.get()
        self.speed_label.config(text=f"{speed:.0f}%")
        
        if self.teleop:
            # Update teleop speeds based on percentage
            base_linear = 0.2
            base_angular = 0.6
            factor = speed / 100.0
            self.teleop.linear_speed_scaling = base_linear * factor
            self.teleop.angular_speed_scaling = base_angular * factor
            
    def update_button_states(self):
        robot_connected = self.robot is not None
        controller_connected = self.controller_connected
        can_start = robot_connected and controller_connected and not self.running
        
        self.start_btn.config(state="normal" if can_start else "disabled")
        self.stop_btn.config(state="normal" if self.running else "disabled")
        self.record_btn.config(state="normal" if self.running else "disabled")
        
    def start_control(self):
        if not self.robot or not self.controller_connected:
            messagebox.showerror("Error", "Robot and controller must be connected")
            return
            
        try:
            print("Initializing teleoperation...")
            self.log_status("Initializing teleoperation...")
            
            self.teleop = GameControllerTeleop(self.robot, 20, XBox360Layout)
            self.update_speed_label()  # Apply current speed setting
            
            print("Starting control loop...")
            self.running = True
            self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
            self.control_thread.start()
            
            self.update_button_states()
            print("Robot control started successfully")
            self.log_status("Robot control started - Use Xbox controller to move robot")
            
        except Exception as e:
            error_msg = f"Failed to start control: {str(e)}"
            print(f"Control start error: {error_msg}")
            messagebox.showerror("Error", error_msg)
            self.log_status(f"Control start failed: {str(e)}")
            
    def stop_control(self):
        self.running = False
        if self.control_thread:
            self.control_thread.join(timeout=2.0)
            
        if self.is_recording:
            self.toggle_recording()
            
        self.teleop = None
        self.update_button_states()
        self.log_status("Robot control stopped")
        
    def control_loop(self):
        print("Control loop started")
        try:
            while self.running:
                if self.teleop:
                    twist = self.teleop.read_twist_and_servo_to_target_position()
                    self.teleop.read_gripper_delta_and_move_gripper()
                    
                    if self.is_recording:
                        self.record_data_point(twist)
                        
                time.sleep(1/20)  # 20 Hz control rate
                
        except Exception as e:
            error_msg = f"Control loop error: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.log_status(error_msg)
            self.running = False
        
        print("Control loop ended")
            
    def toggle_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.recording_data = []
            self.record_btn.config(text="Stop Recording")
            self.record_status.config(text="Recording...", foreground="red")
            self.save_btn.config(state="disabled")
            self.log_status("Recording started")
        else:
            self.is_recording = False
            self.record_btn.config(text="Start Recording")
            self.record_status.config(text=f"Recorded {len(self.recording_data)} points", foreground="blue")
            self.save_btn.config(state="normal")
            self.log_status(f"Recording stopped - {len(self.recording_data)} data points")
            
    def record_data_point(self, twist):
        if self.robot:
            data_point = {
                'timestamp': time.time(),
                'tcp_pose': self.robot.get_tcp_pose().tolist(),
                'twist': twist.tolist(),
                'gripper_width': self.robot.gripper.get_current_width() if self.robot.gripper else None
            }
            self.recording_data.append(data_point)
            
    def save_recording(self):
        if not self.recording_data:
            messagebox.showwarning("Warning", "No recording data to save")
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ur3e_recording_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump({
                    'metadata': {
                        'robot_ip': self.robot_combo.get(),
                        'recording_time': timestamp,
                        'data_points': len(self.recording_data)
                    },
                    'data': self.recording_data
                }, f, indent=2)
                
            self.log_status(f"Recording saved to {filename}")
            messagebox.showinfo("Success", f"Recording saved to {filename}")
            self.save_btn.config(state="disabled")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save recording: {str(e)}")
            self.log_status(f"Save failed: {str(e)}")
            
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
        
    def on_closing(self):
        if self.running:
            self.stop_control()
        if self.scanning:
            self.stop_scan()
        self.root.destroy()


if __name__ == "__main__":
    app = UR3eTeleopGUI()
    app.run()
