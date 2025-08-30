#!/bin/bash
# Start the PDF Tracker application

# Change to the script directory
cd "$(dirname "$0")"

# Make sure the Python scripts are executable
chmod +x pdf_tracker.py
chmod +x pdf_grid_gui.py

# Start the GUI application
python3 pdf_grid_gui.py