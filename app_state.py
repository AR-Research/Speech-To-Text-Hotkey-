# app_state.py
import threading

class AppState:
    def __init__(self):
        self.listening_enabled = True
        self.exit_requested = False
        self.is_recording = False # For tray icon state
        self.active_window_title_on_press: str | None = None
        self.status_message = "Idle" # For tray tooltip or potential notifications
        self.lock = threading.Lock() # For thread-safe access if needed, though simple flags are often fine

    def update_status(self, message: str, is_recording: bool | None = None):
        with self.lock:
            self.status_message = message
            if is_recording is not None:
                self.is_recording = is_recording
        print(f"APP_STATE: {message}, Recording: {self.is_recording}")

    def set_recording(self, recording: bool):
        with self.lock:
            self.is_recording = recording
            self.status_message = "Recording..." if recording else "Processing..."
        print(f"APP_STATE: Recording set to {recording}. Status: {self.status_message}")

    def set_active_window(self, title: str | None):
        with self.lock:
            self.active_window_title_on_press = title