#!/usr/bin/env python3

import sys
import os

# Add the airo_teleop module to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'airo_teleop'))

from airo_teleop.ur3e_teleop_gui import UR3eTeleopGUI

if __name__ == "__main__":
    print("Starting UR3e Teleoperation GUI...")
    app = UR3eTeleopGUI()
    app.run()
