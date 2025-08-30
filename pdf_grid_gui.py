#!/usr/bin/env python3
import sys
import os
import json
import datetime
import subprocess
import logging
import signal
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QLabel, QPushButton, 
                             QFrame, QDialog, QProgressBar, QSystemTrayIcon,
                             QMenu, QAction, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import QColor, QPalette, QFont, QIcon

from pdf_tracker import PDFTracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=os.path.expanduser('~/.pdf_tracker_gui.log'),
    filemode='a'
)

# Colors for the contribution grid (from light to dark green)
COLORS = [
    "#ebedf0",  # Light gray (no contributions)
    "#9be9a8",  # Light green (some contributions)
    "#40c463",  # Medium green
    "#30a14e",  # Darker green
    "#216e39"   # Darkest green
]

class ContributionSquare(QFrame):
    """A single square in the contribution grid"""
    clicked = pyqtSignal(str)  # Signal to emit the date when clicked
    
    def __init__(self, date, minutes=0, target_minutes=60):
        super().__init__()
        self.date = date
        self.minutes = minutes
        self.target_minutes = target_minutes
        self.max_minutes = 180  # Maximum minutes (3 hours) for color scaling
        self.min_threshold = 30  # Minimum minutes before color changes
        self.setFixedSize(16, 16)  # Use fixed size instead of min/max
        self.setToolTip(f"{date}: {int(minutes)} minutes")
        self.update_color()
        
        # Make the squares clickable
        self.setFrameShape(QFrame.Box)
        self.setCursor(Qt.PointingHandCursor)
    
    def update_color(self):
        color_index = 0  # Default white/gray for under 30 minutes
        
        if self.minutes >= self.min_threshold:
            # Calculate how far between min_threshold and max_minutes
            effective_minutes = min(self.minutes, self.max_minutes)
            # Scale between min_threshold and max_minutes
            progress = (effective_minutes - self.min_threshold) / (self.max_minutes - self.min_threshold)
            # Map to color indices 1-4 (color range is 0-4, but 0 is reserved for < 30 min)
            color_index = max(1, min(4, 1 + int(progress * 3)))
            
        palette = self.palette()
        palette.setColor(QPalette.Background, QColor(COLORS[color_index]))
        self.setAutoFillBackground(True)
        self.setPalette(palette)
        
        # Update tooltip with time and thresholds
        time_desc = f"{int(self.minutes)} minutes"
        if self.minutes < self.min_threshold:
            status = f"({int(self.min_threshold - self.minutes)} min to reach next level)"
        elif self.minutes < self.max_minutes:
            status = f"({int(self.max_minutes - self.minutes)} min to max level)"
        else:
            status = "(Maximum level reached!)"
        
        self.setToolTip(f"{self.date}: {time_desc}\n{status}")
    
    def update_minutes(self, minutes):
        self.minutes = minutes
        self.update_color()
    
    def mousePressEvent(self, event):
        self.clicked.emit(self.date)
        super().mousePressEvent(event)

class ContributionGrid(QWidget):
    """Widget displaying a GitHub-style contribution grid"""
    
    def __init__(self, tracker):
        super().__init__()
        self.tracker = tracker
        self.squares = {}  # Dictionary mapping dates to ContributionSquare widgets
        
        # Create the layout
        self.main_layout = QVBoxLayout(self)
        
        # Add month labels
        month_widget = QWidget()
        self.month_layout = QHBoxLayout(month_widget)
        self.month_layout.setContentsMargins(35, 0, 0, 0)  # Add left margin for alignment
        self.main_layout.addWidget(month_widget)
        
        # Add day of week labels and grid
        grid_widget = QWidget()
        self.grid_container = QHBoxLayout(grid_widget)
        self.grid_container.setContentsMargins(0, 0, 0, 0)
        
        # Day of week labels
        dow_widget = QWidget()
        self.dow_layout = QVBoxLayout(dow_widget)
        self.dow_layout.setContentsMargins(0, 0, 0, 0)
        days = ["Mon", "Wed", "Fri"]
        for day in days:
            label = QLabel(day)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            label.setFixedWidth(30)
            self.dow_layout.addWidget(label)
            if day != "Fri":
                self.dow_layout.addWidget(QLabel(""))  # Spacer
                
        self.grid_container.addWidget(dow_widget)
        
        # The actual grid
        grid_layout_widget = QWidget()
        self.grid_layout = QGridLayout(grid_layout_widget)
        self.grid_layout.setSpacing(2)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_container.addWidget(grid_layout_widget)
        self.main_layout.addWidget(grid_widget)
        
        # Status bar
        self.status_bar = QHBoxLayout()
        self.status_label = QLabel("Not tracking any PDF")
        self.status_bar.addWidget(self.status_label)
        
        # Progress bar for today
        progress_widget = QWidget()
        self.progress_layout = QHBoxLayout(progress_widget)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_label = QLabel("Today's progress:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(20)  # Set fixed height for progress bar
        self.progress_layout.addWidget(self.progress_label)
        self.progress_layout.addWidget(self.progress_bar)
        
        self.main_layout.addWidget(progress_widget)
        
        # Status bar in its own widget
        status_widget = QWidget()
        self.status_bar = QHBoxLayout(status_widget)
        self.status_bar.setContentsMargins(0, 0, 0, 0)
        self.status_label = QLabel("Not tracking any PDF")
        self.status_bar.addWidget(self.status_label)
        self.main_layout.addWidget(status_widget)
        
        # Create the grid squares for the past year
        self.initialize_grid()
        
        # Update the grid with actual data
        self.update_grid_data()
        
        # Set up a timer to update the grid
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_grid_data)
        self.timer.start(10000)  # Update every 10 seconds
    
    def initialize_grid(self):
        """Initialize the grid with empty squares"""
        today = datetime.datetime.now().date()
        
        # Calculate the first day of the grid (52 weeks ago)
        start_date = today - datetime.timedelta(days=364)
        
        # Find the first Monday
        while start_date.weekday() != 0:  # 0 is Monday
            start_date += datetime.timedelta(days=1)
        
        # Add month labels
        current_month = None
        month_labels = {}
        
        # Fill the grid
        for week in range(53):  # 52 weeks plus current week
            for day in range(7):  # 7 days per week
                current_date = start_date + datetime.timedelta(days=(week * 7 + day))
                
                # Skip future dates
                if current_date > today:
                    continue
                
                # Track month changes for labels
                if current_month != current_date.month:
                    current_month = current_date.month
                    month_labels[week] = current_date.strftime("%b")
                
                # Create the square
                date_str = current_date.strftime("%Y-%m-%d")
                square = ContributionSquare(date_str)
                square.clicked.connect(self.show_date_details)
                
                # Add to grid and track in dictionary
                # Use a fixed column width to prevent layout issues
                self.grid_layout.addWidget(square, day, week)
                self.grid_layout.setColumnMinimumWidth(week, 18)
                self.grid_layout.setRowMinimumHeight(day, 18)
                self.squares[date_str] = square
        
        # Add month labels - improved positioning
        prev_week = 0
        for week, month in month_labels.items():
            if week > 0:
                # Add spacing between month labels
                spacing = (week - prev_week) * 18
                if spacing > 0:
                    spacer = QWidget()
                    spacer.setFixedWidth(spacing)
                    self.month_layout.addWidget(spacer)
            
            label = QLabel(month)
            label.setAlignment(Qt.AlignCenter)
            self.month_layout.addWidget(label)
            prev_week = week
            
        # Add stretch to align month labels properly
        self.month_layout.addStretch()
    
    def update_grid_data(self):
        """Update grid with actual tracking data"""
        # Get tracking data
        history = self.tracker.get_history()
        status = self.tracker.get_status()
        
        # Update the grid squares
        for date, data in history.items():
            if date in self.squares:
                self.squares[date].update_minutes(data["minutes"])
        
        # Update status display
        if status["active_session"]:
            self.status_label.setText(f"Tracking: {status['current_pdf'] or 'a PDF document'}")
            
            # Calculate progress percentage based on which threshold we're working toward
            if status["minutes"] >= status["max_minutes"]:
                # Max level reached - show 100%
                progress_pct = 100
                self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #216e39; }")
            elif status["minutes"] >= status["target_minutes"]:
                # Between target and max
                progress_pct = 60 + min(40, int(((status["minutes"] - status["target_minutes"]) / 
                                     (status["max_minutes"] - status["target_minutes"])) * 40))
                self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #40c463; }")
            elif status["minutes"] >= status["min_minutes"]:
                # Between min and target
                progress_pct = 30 + min(30, int(((status["minutes"] - status["min_minutes"]) / 
                                     (status["target_minutes"] - status["min_minutes"])) * 30))
                self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #9be9a8; }")
            else:
                # Below minimum threshold
                progress_pct = min(30, int((status["minutes"] / status["min_minutes"]) * 30))
                self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #ebedf0; }")
            
            self.progress_bar.setValue(progress_pct)
            
            # Update today's square in real-time
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            if today in self.squares:
                self.squares[today].update_minutes(status["minutes"])
        else:
            self.status_label.setText("Not tracking any PDF currently")
    
    def show_date_details(self, date):
        """Show details for the clicked date"""
        if date in self.tracker.data["days"]:
            minutes = self.tracker.data["days"][date]
            target = self.tracker.config["min_time_minutes"]
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Reading on {date}")
            layout = QVBoxLayout(dialog)
            
            layout.addWidget(QLabel(f"Date: {date}"))
            layout.addWidget(QLabel(f"Reading time: {int(minutes)} minutes"))
            layout.addWidget(QLabel(f"Daily target: {target} minutes"))
            
            status = "✅ Completed" if minutes >= target else "❌ Not completed"
            status_label = QLabel(status)
            status_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(status_label)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            
            dialog.setLayout(layout)
            dialog.exec_()

class PDFTrackerApp(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.tracker = PDFTracker()
        self.init_ui()
        
        # Start the tracker in a separate process if not already running
        self.ensure_tracker_daemon()
        
        # Create system tray icon
        self.create_tray_icon()
    
    def init_ui(self):
        self.setWindowTitle("PDF Reading Tracker")
        self.setMinimumSize(900, 400)  # Increased size to accommodate grid
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)  # Add margins around the entire layout
        
        # Add title
        title_label = QLabel("PDF Reading Contribution Tracker")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)
        
        # Add explanation
        explanation = QLabel("Each square represents a day. The color indicates your reading time.")
        explanation.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(explanation)
        
        # Add spacing
        main_layout.addSpacing(10)
        
        # Add contribution grid
        self.grid_widget = ContributionGrid(self.tracker)
        main_layout.addWidget(self.grid_widget)
        
        # Add spacing
        main_layout.addSpacing(10)
        
        # Add legend with thresholds
        legend_widget = QWidget()
        legend_layout = QHBoxLayout(legend_widget)
        legend_layout.setContentsMargins(0, 0, 0, 0)
        
        # Get thresholds from tracker
        min_minutes = self.tracker.config["min_time_minutes"]
        target_minutes = self.tracker.config["target_time_minutes"]
        max_minutes = self.tracker.config["max_time_minutes"]
        
        # Create labels with time thresholds
        legend_layout.addWidget(QLabel(f"<{min_minutes}m"))
        
        for i, color in enumerate(COLORS):
            square = QFrame()
            square.setFixedSize(15, 15)
            square.setAutoFillBackground(True)
            palette = square.palette()
            palette.setColor(QPalette.Background, QColor(color))
            square.setPalette(palette)
            square.setFrameShape(QFrame.Box)
            legend_layout.addWidget(square)
            
            # Add threshold labels
            if i == 0:
                legend_layout.addWidget(QLabel(f"{min_minutes}m"))
            elif i == 1:
                legend_layout.addWidget(QLabel(f"{target_minutes}m"))
            elif i == 3:
                legend_layout.addWidget(QLabel(f"{max_minutes}m+"))
        
        legend_layout.addStretch()
        main_layout.addWidget(legend_widget)
        
        # Set up a timer to update the status
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_status)
        self.timer.start(5000)  # Update every 5 seconds
    
    def create_tray_icon(self):
        """Create system tray icon and menu"""
        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self)
        
        # Try to use a document icon, fall back to system default if not found
        try:
            self.tray_icon.setIcon(QIcon.fromTheme("accessories-document"))
        except:
            self.tray_icon.setIcon(QIcon.fromTheme("dialog-information"))
        
        # Create tray menu
        tray_menu = QMenu()
        
        # Add actions to the menu
        show_action = QAction("Show Tracker", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        status_action = QAction("Check Status", self)
        status_action.triggered.connect(self.check_status)
        tray_menu.addAction(status_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        # Set the menu
        self.tray_icon.setContextMenu(tray_menu)
        
        # Show icon
        self.tray_icon.show()
        
        # Connect signal to show message when clicked
        self.tray_icon.activated.connect(self.tray_icon_activated)
    
    def tray_icon_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.Trigger:
            status = self.tracker.get_status()
            
            if status["active_session"]:
                self.tray_icon.showMessage(
                    "PDF Reading Tracker", 
                    f"Today: {int(status['minutes'])} minutes of reading\n"
                    f"Target: {int(status['target_minutes'])} minutes "
                    f"({'✓' if status['target_reached'] else '✗'})",
                    QSystemTrayIcon.Information, 
                    3000
                )
            else:
                self.tray_icon.showMessage(
                    "PDF Reading Tracker", 
                    "No active reading session detected",
                    QSystemTrayIcon.Information, 
                    3000
                )
    
    def check_status(self):
        """Show status dialog with current reading info"""
        status = self.tracker.get_status()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("PDF Reading Status")
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel(f"Date: {status['date']}"))
        layout.addWidget(QLabel(f"Reading time today: {int(status['minutes'])} minutes"))
        
        # Add progress information based on thresholds
        if status['level'] == 0:
            # Below minimum threshold
            remaining = status['min_minutes'] - status['minutes']
            threshold_label = QLabel(f"Need {int(remaining)} more minutes to reach first level ({status['min_minutes']} min)")
            threshold_label.setStyleSheet("color: #888;")
            level_text = "Not reached minimum time yet"
        elif status['level'] == 1:
            # Between min and target
            remaining = status['target_minutes'] - status['minutes']
            threshold_label = QLabel(f"Need {int(remaining)} more minutes to reach second level ({status['target_minutes']} min)")
            threshold_label.setStyleSheet("color: #9be9a8;")
            level_text = "✅ Reached minimum reading time"
        elif status['level'] == 2:
            # Between target and max
            remaining = status['max_minutes'] - status['minutes']
            threshold_label = QLabel(f"Need {int(remaining)} more minutes to reach maximum level ({status['max_minutes']} min)")
            threshold_label.setStyleSheet("color: #40c463;")
            level_text = "✅✅ Reached target reading time"
        else:
            # At or above max
            threshold_label = QLabel(f"Reached maximum reading level! ({status['max_minutes']} min)")
            threshold_label.setStyleSheet("color: #216e39; font-weight: bold;")
            level_text = "✅✅✅ Reached maximum reading time"
        
        layout.addWidget(QLabel("Reading levels:"))
        layout.addWidget(QLabel(f"• Level 1: {status['min_minutes']} minutes"))
        layout.addWidget(QLabel(f"• Level 2: {status['target_minutes']} minutes"))
        layout.addWidget(QLabel(f"• Level 3: {status['max_minutes']} minutes (maximum)"))
        
        layout.addWidget(threshold_label)
        
        status_label = QLabel(level_text)
        status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(status_label)
        
        if status['active_session']:
            active_label = QLabel(f"Currently reading: {status['current_pdf'] or 'a PDF document'}")
            active_label.setStyleSheet("color: green;")
            layout.addWidget(active_label)
        else:
            layout.addWidget(QLabel("No active reading session"))
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def ensure_tracker_daemon(self):
        """Make sure the tracker daemon is running"""
        # Check if the daemon is already running using PID file
        pid_file = os.path.expanduser("~/.pdf_tracker.pid")
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                try:
                    pid = int(f.read().strip())
                    os.kill(pid, 0)  # Check if process is running
                    logging.info(f"Tracker daemon already running (PID: {pid})")
                    return
                except (OSError, ValueError):
                    # Process not running or invalid PID, remove stale PID file
                    os.remove(pid_file)
        
        # Start the tracker daemon
        try:
            subprocess.Popen(
                ["python3", os.path.join(os.path.dirname(__file__), "pdf_tracker.py")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logging.info("Started tracker daemon")
        except Exception as e:
            logging.error(f"Error starting tracker daemon: {e}")
            QMessageBox.warning(
                self, 
                "Tracker Error", 
                f"Could not start the PDF tracker daemon: {e}"
            )
    
    def update_status(self):
        """Update the status from the tracker"""
        self.grid_widget.update_grid_data()
        
        # Check if tracker daemon is still running
        self.ensure_tracker_daemon()
    
    def quit_application(self):
        """Clean up and quit the application"""
        # Don't kill the daemon when quitting, let it run in the background
        QApplication.quit()
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.tray_icon.isVisible():
            # Just hide the window, don't close the app
            self.hide()
            self.tray_icon.showMessage(
                "PDF Reading Tracker", 
                "The application is still running in the background.\n"
                "Click the tray icon to show it again.",
                QSystemTrayIcon.Information, 
                3000
            )
            event.ignore()
        else:
            event.accept()

def is_application_running():
    """Check if another instance of the application is running"""
    lock_file = os.path.expanduser("~/.pdf_tracker_gui.lock")
    
    if os.path.exists(lock_file):
        # Check if the process is still running
        with open(lock_file, "r") as f:
            try:
                pid = int(f.read().strip())
                os.kill(pid, 0)  # This will raise OSError if the process is not running
                return True
            except (OSError, ValueError):
                # Process not running or invalid PID
                pass
    
    # Create lock file with current PID
    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))
    
    return False

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Don't quit when window closed, due to tray icon
    
    # Set application name for settings
    app.setApplicationName("PDF Reading Tracker")
    
    # Check if application is already running
    if is_application_running():
        QMessageBox.information(None, "Already Running", 
                               "PDF Reading Tracker is already running.\n"
                               "Please check your system tray.")
        sys.exit(1)
    
    window = PDFTrackerApp()
    window.show()
    
    # Clean up lock file on exit
    app.aboutToQuit.connect(lambda: os.remove(os.path.expanduser("~/.pdf_tracker_gui.lock")))
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()