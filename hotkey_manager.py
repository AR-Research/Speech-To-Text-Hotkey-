# hotkey_manager.py
import threading
from pynput import keyboard
import pyautogui
import time
import os
import winsound

# Assuming these are in the same directory or properly pathed
from app_state import AppState
from audio_recorder import AudioRecorder
from stt_engine import transcribe_audio_file
from text_inserter import insert_text_at_cursor

# Define the hotkey combination (Ctrl + Alt)
# Using sets for robust detection of concurrent presses
HOTKEY_COMBINATION_PRESS = {keyboard.Key.ctrl_l, keyboard.Key.alt_l}
# Alternative/Additional: 
# HOTKEY_COMBINATION_PRESS_R = {keyboard.Key.ctrl_r, keyboard.Key.alt_r}

# To detect release of EITHER Ctrl or Alt when the combo was active
HOTKEY_PARTIAL_RELEASE = {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.Key.ctrl_r, keyboard.Key.alt_r}


class HotkeyManager:
    def __init__(self, app_state: AppState, audio_recorder: AudioRecorder, tray_icon_ref=None):
        self.app_state = app_state
        self.audio_recorder = audio_recorder
        self.listener_thread = None
        self.pynput_listener = None
        self.currently_pressed_keys = set()
        self._hotkey_active_and_recording = False # State to manage if we are in a hotkey-triggered recording session
        self.tray_icon = tray_icon_ref # pystray.Icon object

    def _update_tray_feedback(self):
        """Update tray icon and title based on app_state."""
        if self.tray_icon:
            # Assuming get_icon_for_state is available or logic is here
            # This function would ideally be in main.py and passed as a callback
            # For now, direct update attempt (pystray is usually okay with icon/title from threads)
            from main import get_icon_for_state # Circular import risk, better to pass callback
            
            current_status = "idle"
            if not self.app_state.listening_enabled:
                current_status = "disabled"
            elif self.app_state.is_recording:
                current_status = "recording"
            elif "processing..." in self.app_state.status_message.lower(): # Check for processing state
                current_status = "processing"
            elif "error" in self.app_state.status_message.lower():
                current_status = "error_generic" # Or more specific error states

            self.tray_icon.icon = get_icon_for_state(current_status)
            self.tray_icon.title = f"Voice-to-Text: {self.app_state.status_message}"


    def _on_press(self, key):
        if not self.app_state.listening_enabled or self.app_state.exit_requested:
            return True 

        is_left_ctrl = key == keyboard.Key.ctrl_l
        is_left_alt = key == keyboard.Key.alt_l
        
        if is_left_ctrl or is_left_alt: 
            self.currently_pressed_keys.add(key)

        if HOTKEY_COMBINATION_PRESS.issubset(self.currently_pressed_keys):
            if not self._hotkey_active_and_recording: 
                print("HotkeyManager: Ctrl+Alt PRESSED and HELD.")
                self._hotkey_active_and_recording = True
                
                # --- Play sound to indicate recording start ---
                try:
                    # Option A: Simple beep (frequency in Hz, duration in milliseconds)
                    winsound.Beep(1000, 150) # Example: 1000 Hz for 150 ms
                    # You can experiment with different frequencies and durations
                    # e.g., winsound.Beep(800, 100) for a softer/shorter beep
                except Exception as e_sound:
                    print(f"HotkeyManager: Error playing start sound: {e_sound}")
                # --- End of sound playback ---

                self.app_state.set_recording(True) 

                try:
                    active_window = pyautogui.getActiveWindow()
                    title = active_window.title if active_window else None
                    self.app_state.set_active_window(title)
                    print(f"HotkeyManager: Active window on press: '{title}'")
                except Exception as e:
                    print(f"HotkeyManager: Error getting active window: {e}")
                    self.app_state.set_active_window(None)
                
                self.audio_recorder.start_recording()
        return True

    def _on_release(self, key):
        if self.app_state.exit_requested:
            return False # Stop listener if exiting

        # Remove released key from the set
        if key in self.currently_pressed_keys:
            self.currently_pressed_keys.remove(key)
            print(f"HotkeyManager: Released {key}. Currently pressed: {self.currently_pressed_keys}")

        # If one of the hotkey components is released AND we were recording due to hotkey
        if key in HOTKEY_PARTIAL_RELEASE and self._hotkey_active_and_recording:
            # Check if the hotkey combo is effectively broken
            # This happens if NOT ALL required keys are still in currently_pressed_keys
            # A simpler check: if any of the *original* hotkey set is released, sequence ends.
            # We initiated recording when HOTKEY_COMBINATION_PRESS was met.
            # So, if any key from that set is released, the "hold" is over.
            
            print(f"HotkeyManager: Monitored key {key} RELEASED while recording was active.")
            self.app_state.set_recording(False) # is_recording=False, status="Processing..."
            # self._update_tray_feedback()


            audio_file = self.audio_recorder.stop_recording()
            self._hotkey_active_and_recording = False # Reset for next hotkey press
            # self.currently_pressed_keys.clear() # Clear all, as the combo is broken. Or let press manage.

            active_window_title_for_typing = self.app_state.active_window_title_on_press
            self.app_state.set_active_window(None) # Clear it after use

            if audio_file:
                self.app_state.update_status(f"Transcribing {os.path.basename(audio_file)}...", is_recording=False)
                # self._update_tray_feedback()

                transcribed_text = transcribe_audio_file(audio_file)
                
                # Clean up temporary audio file
                try:
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                        print(f"HotkeyManager: Deleted temporary audio file: {audio_file}")
                except Exception as e:
                    print(f"HotkeyManager ERROR: Could not delete temp audio file {audio_file}: {e}")

                if transcribed_text and not transcribed_text.lower().startswith("error:"):
                    self.app_state.update_status(f"Typing: '{transcribed_text[:30]}...'")
                    # self._update_tray_feedback()
                    time.sleep(0.1) # Brief pause before typing
                    success = insert_text_at_cursor(transcribed_text, active_window_title_for_typing)
                    if success:
                        self.app_state.update_status("Text inserted successfully.")
                    else:
                        self.app_state.update_status("Error inserting text.")
                else:
                    error_message = transcribed_text if transcribed_text else "Transcription failed: Unknown error."
                    self.app_state.update_status(error_message)
            else:
                self.app_state.update_status("Audio recording failed.")
            
            # self._update_tray_feedback()
            # Reset keys for next full press sequence
            self.currently_pressed_keys.clear()


        return True # Keep listener running unless exit_requested

    def run_listener(self):
        print("HotkeyManager: Starting keyboard listener...")
        try:
            # Non-blocking listener using new thread for callbacks is default for pynput
            # For global hotkeys, listener usually needs to run in a way that doesn't block main GUI thread
            # The .join() makes it blocking.
            self.pynput_listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self.pynput_listener.start() # Start the listener thread
            print("HotkeyManager: Keyboard listener thread started.")
            # Keep this thread alive while app runs, or join if run method is meant to block
            while not self.app_state.exit_requested:
                time.sleep(0.1) # Keep thread alive and check for exit
            print("HotkeyManager: Exit requested, stopping listener thread.")
            if self.pynput_listener and self.pynput_listener.is_alive():
                 self.pynput_listener.stop()

        except Exception as e:
            print(f"HotkeyManager ERROR: Failed to start or run listener: {e}")
            import traceback
            traceback.print_exc()
            self.app_state.update_status(f"Listener Error: {e}")
            # self._update_tray_feedback()


    def start(self):
        if self.listener_thread and self.listener_thread.is_alive():
            print("HotkeyManager: Listener already running.")
            return
        
        # Reset states before starting
        self.app_state.exit_requested = False 
        self.currently_pressed_keys.clear()
        self._hotkey_active_and_recording = False

        self.listener_thread = threading.Thread(target=self.run_listener, daemon=True)
        self.listener_thread.start()

    def stop(self):
        print("HotkeyManager: Stop requested.")
        self.app_state.exit_requested = True # Signal run_listener loop to exit
        if self.pynput_listener:
            print("HotkeyManager: Stopping pynput listener...")
            try:
                # This might not be strictly necessary if the thread exits cleanly,
                # but good for explicit cleanup.
                self.pynput_listener.stop() # Tell the listener to stop
            except Exception as e:
                print(f"HotkeyManager: Error stopping pynput listener: {e}")
        
        if self.listener_thread and self.listener_thread.is_alive():
            print("HotkeyManager: Waiting for listener thread to join...")
            self.listener_thread.join(timeout=1.0) # Wait for thread to finish
            if self.listener_thread.is_alive():
                print("HotkeyManager WARN: Listener thread did not join in time.")
        print("HotkeyManager: Stopped.")