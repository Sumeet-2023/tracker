#!/usr/bin/env python3
import os
import time
import json
import datetime
import subprocess
import signal
import sys
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=os.path.expanduser('~/.pdf_tracker.log'),
    filemode='a'
)

class PDFTracker:
    def __init__(self, config_file=None):
        self.home_dir = os.path.expanduser("~")
        self.config_file = config_file or os.path.join(self.home_dir, ".pdf_tracker_config.json")
        self.data_file = os.path.join(self.home_dir, ".pdf_tracker_data.json")
        
        # Load or create configuration
        self.config = self._load_config()
        
        # Load or create tracking data
        self.data = self._load_data()
    
    def _load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        else:
            # Default configuration
            default_config = {
                "target_apps": ["evince", "atril", "okular", "xreader", "document-viewer"],
                "min_time_minutes": 30,  # 30 minutes for first green level
                "target_time_minutes": 60,  # 1 hour for medium green
                "max_time_minutes": 180,  # 3 hours for maximum green
                "check_interval": 10,  # seconds between checks
            }
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def _load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                return json.load(f)
        else:
            # Create empty data structure
            empty_data = {
                "days": {},  # will contain date -> minutes mapping
                "last_check": None,
                "current_session": {
                    "start": None,
                    "pdf_path": None,
                    "accumulated_time": 0
                }
            }
            with open(self.data_file, 'w') as f:
                json.dump(empty_data, f, indent=2)
            return empty_data
    
    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def is_pdf_viewer_running(self):
        """Check if any of the target PDF viewer apps are running"""
        for app in self.config["target_apps"]:
            try:
                output = subprocess.check_output(["pgrep", app])
                if output:
                    # Try to get the currently open PDF file
                    try:
                        proc_info = subprocess.check_output(["ps", "aux"]).decode('utf-8')
                        if app in proc_info and ".pdf" in proc_info:
                            # This is a very simplified approach - might need refinement
                            for line in proc_info.split('\n'):
                                if app in line and ".pdf" in line:
                                    pdf_parts = [part for part in line.split() if ".pdf" in part]
                                    if pdf_parts:
                                        return True, pdf_parts[0]
                        return True, None  # App is running but can't determine PDF
                    except:
                        return True, None  # App is running but can't determine PDF
            except subprocess.CalledProcessError:
                continue
        return False, None
    
    def track_session(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Initialize today's entry if it doesn't exist
        if today not in self.data["days"]:
            self.data["days"][today] = 0
            
        is_running, pdf_path = self.is_pdf_viewer_running()
        
        if is_running:
            current_time = time.time()
            
            # Start new session or continue current
            if self.data["current_session"]["start"] is None:
                self.data["current_session"]["start"] = current_time
                self.data["current_session"]["pdf_path"] = pdf_path
                self.data["current_session"]["accumulated_time"] = 0
            else:
                # Calculate time since last check
                if self.data["last_check"]:
                    elapsed = current_time - self.data["last_check"]
                    self.data["current_session"]["accumulated_time"] += elapsed
                    
                    # Add time to today's total
                    self.data["days"][today] += elapsed / 60  # Convert to minutes
        else:
            # Reset current session if viewer is not running
            self.data["current_session"]["start"] = None
            self.data["current_session"]["pdf_path"] = None
            self.data["current_session"]["accumulated_time"] = 0
        
        # Update last check time
        self.data["last_check"] = time.time()
        
        # Save updated data
        self.save_data()
        
        return self.get_status()
    
    def get_status(self):
        """Return current tracking status"""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        minutes_today = self.data["days"].get(today, 0)
        
        # Determine level based on minutes read
        if minutes_today >= self.config["max_time_minutes"]:
            level = 3  # Maximum level
        elif minutes_today >= self.config["target_time_minutes"]:
            level = 2  # Medium level
        elif minutes_today >= self.config["min_time_minutes"]:
            level = 1  # Minimum level
        else:
            level = 0  # No level reached yet
            
        target_reached = minutes_today >= self.config["min_time_minutes"]
        
        return {
            "date": today,
            "minutes": minutes_today,
            "level": level,
            "target_reached": target_reached,
            "min_minutes": self.config["min_time_minutes"],
            "target_minutes": self.config["target_time_minutes"],
            "max_minutes": self.config["max_time_minutes"],
            "active_session": self.data["current_session"]["start"] is not None,
            "current_pdf": self.data["current_session"]["pdf_path"]
        }
    
    def get_history(self, days=365):
        """Return reading history for the specified number of days"""
        history = {}
        today = datetime.datetime.now().date()
        
        for i in range(days):
            date_key = (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            minutes = self.data["days"].get(date_key, 0)
            
            # Determine level based on minutes read
            if minutes >= self.config["max_time_minutes"]:
                level = 3  # Maximum level
            elif minutes >= self.config["target_time_minutes"]:
                level = 2  # Medium level
            elif minutes >= self.config["min_time_minutes"]:
                level = 1  # Minimum level
            else:
                level = 0  # No level reached yet
                
            target_reached = minutes >= self.config["min_time_minutes"]
            
            history[date_key] = {
                "minutes": minutes,
                "level": level,
                "target_reached": target_reached
            }
        
        return history

def daemonize():
    """Daemonize the current process"""
    # First fork
    try:
        pid = os.fork()
        if pid > 0:
            # Exit first parent
            sys.exit(0)
    except OSError as e:
        logging.error(f"Fork #1 failed: {e}")
        sys.exit(1)
    
    # Decouple from parent environment
    os.chdir('/')
    os.setsid()
    os.umask(0)
    
    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            # Exit second parent
            sys.exit(0)
    except OSError as e:
        logging.error(f"Fork #2 failed: {e}")
        sys.exit(1)
    
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    
    # Create a PID file
    pid_file = os.path.expanduser("~/.pdf_tracker.pid")
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

def handle_signal(signum, frame):
    """Handle termination signals"""
    pid_file = os.path.expanduser("~/.pdf_tracker.pid")
    if os.path.exists(pid_file):
        os.remove(pid_file)
    logging.info("PDF Tracker daemon stopped")
    sys.exit(0)

def start_tracker_daemon(daemon_mode=True):
    """Run the tracker as a background process"""
    if daemon_mode:
        # Check if daemon is already running
        pid_file = os.path.expanduser("~/.pdf_tracker.pid")
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 0)  # Check if process is running
                logging.info(f"PDF Tracker daemon is already running (PID: {pid})")
                return
            except OSError:
                # Process not running, remove stale PID file
                os.remove(pid_file)
        
        # Daemonize
        daemonize()
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
    
    tracker = PDFTracker()
    logging.info("PDF Tracker daemon started")
    
    try:
        while True:
            status = tracker.track_session()
            if status["active_session"]:
                logging.info(f"Tracking: {status['minutes']:.1f} minutes today " +
                     f"({'✓' if status['target_reached'] else '✗'})")
            else:
                logging.debug("No active PDF viewing session detected")
            time.sleep(tracker.config["check_interval"])
    except KeyboardInterrupt:
        logging.info("PDF Tracker daemon stopped")
        if daemon_mode:
            if os.path.exists(pid_file):
                os.remove(pid_file)

if __name__ == "__main__":
    # If running from command line with --no-daemon flag, don't daemonize
    daemon_mode = "--no-daemon" not in sys.argv
    start_tracker_daemon(daemon_mode)