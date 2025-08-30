#!/bin/bash
# Uninstall PDF Reading Tracker

echo "Uninstalling PDF Reading Tracker..."

# Remove desktop entries
if [ -f ~/.local/share/applications/pdf-tracker.desktop ]; then
    rm ~/.local/share/applications/pdf-tracker.desktop
    echo "Removed desktop entry"
fi

# Remove autostart entry
if [ -f ~/.config/autostart/pdf-tracker-daemon.desktop ]; then
    rm ~/.config/autostart/pdf-tracker-daemon.desktop
    echo "Removed autostart entry"
fi

# Stop the daemon
pid_file=~/.pdf_tracker.pid
if [ -f "$pid_file" ]; then
    pid=$(cat "$pid_file")
    if ps -p "$pid" > /dev/null; then
        echo "Stopping tracker daemon..."
        kill "$pid"
    fi
    rm "$pid_file"
fi

# Remove lock file
lock_file=~/.pdf_tracker_gui.lock
if [ -f "$lock_file" ]; then
    rm "$lock_file"
fi

echo "Uninstallation complete."
echo "Note: Configuration and tracking data are still stored in your home directory."
echo "To remove them completely, delete these files:"
echo "  ~/.pdf_tracker_config.json"
echo "  ~/.pdf_tracker_data.json"
echo "  ~/.pdf_tracker.log"
echo "  ~/.pdf_tracker_gui.log"