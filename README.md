# PDF Reading Tracker

A LeetCode-like contribution tracker for monitoring your PDF reading habits. The application tracks time spent reading PDF documents and displays a GitHub-style contribution grid that turns green when you've read for at least an hour in a day.

## Features

- Tracks time spent reading PDF documents in common Linux PDF viewers
- Visual contribution grid similar to GitHub/LeetCode
- Shows daily progress toward your reading goal
- Runs in the background and stays in sync with your reading sessions
- Click on any day to see detailed statistics

## Installation

### Prerequisites

Make sure you have Python 3 and PyQt5 installed:

```bash
sudo apt-get update
sudo apt-get install python3 python3-pip
pip3 install PyQt5
```

### Desktop Installation

1. Run the installation script:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
   
   This will:
   - Make the scripts executable
   - Install a desktop entry so the app appears in your applications menu
   - Set up autostart so the tracker starts when you log in
   - Start the background tracker daemon

2. To uninstall:
   ```bash
   chmod +x uninstall.sh
   ./uninstall.sh
   ```

### Manual Setup (Alternative)

If you don't want to use the installation script:

1. Make the scripts executable:
   ```bash
   chmod +x pdf_tracker.py pdf_grid_gui.py
   ```

2. Install the desktop entry manually:
   ```bash
   mkdir -p ~/.local/share/applications
   cp pdf-tracker.desktop ~/.local/share/applications/
   ```

3. Install autostart entry manually:
   ```bash
   mkdir -p ~/.config/autostart
   cp pdf-tracker-daemon.desktop ~/.config/autostart/
   ```

## Usage

1. After installation, you can find and launch "PDF Reading Tracker" in your applications menu.

2. The tracker runs in the background and will continue running even if you close the main window. You can access it anytime through the system tray icon.

2. Open a PDF document using your preferred PDF viewer (Evince, Atril, Okular, etc.).

3. The tracker will automatically monitor your reading time and update the contribution grid.

4. The squares in the grid will change color based on your reading time:
   - Gray: No reading
   - Light green: Some reading, but less than the target time
   - Darker greens: More reading time, with the darkest green indicating the target has been reached

5. Click on any square to see detailed information about your reading for that day.

## Configuration

The application creates a configuration file at `~/.pdf_tracker_config.json`. You can edit this file to modify:

- Target applications to monitor
- Daily reading time goal (default: 60 minutes)
- Checking interval

## Supported PDF Viewers

By default, the application monitors:
- Evince (default Ubuntu PDF viewer)
- Atril (MATE PDF viewer)
- Okular (KDE PDF viewer)
- XReader
- Generic "document-viewer"

You can add more viewers by editing the configuration file.

## Troubleshooting

If the application doesn't detect your PDF viewer:
1. Make sure the PDF viewer is running
2. Check if your PDF viewer is in the supported list in the configuration file
3. Try running the tracker from the terminal to see debug output

## License

This application is free to use and modify.# tracker
