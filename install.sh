#!/bin/bash
# Install PDF Reading Tracker as a desktop application

# Make sure we're in the right directory
cd "$(dirname "$0")"

echo "Installing PDF Reading Tracker..."

# Make scripts executable
chmod +x pdf_tracker.py pdf_grid_gui.py

# Create autostart directory if it doesn't exist
mkdir -p ~/.config/autostart

# Install autostart entry for the tracker daemon
cp pdf-tracker-daemon.desktop ~/.config/autostart/
echo "Installed autostart entry for background tracker"

# Install desktop entry
mkdir -p ~/.local/share/applications
cp pdf-tracker.desktop ~/.local/share/applications/
echo "Installed desktop entry"

# Start the tracker daemon if not already running
if ! pgrep -f "pdf_tracker.py" > /dev/null; then
    echo "Starting tracker daemon..."
    ./pdf_tracker.py &
fi

echo "Installation complete. You can now find 'PDF Reading Tracker' in your applications menu."
echo "The tracker will automatically start when you log in."
echo "You can also run it manually with: ./pdf_grid_gui.py"