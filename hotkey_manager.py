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
        self.listener_thread: threading.Thread | None = None  # <<< INITIALIZE HERE
        self.pynput_listener: keyboard.Listener | None = None # Also good to initialize with type hint
        self.currently_pressed_keys = set()
        self._hotkey_active_and_recording = False 
        self.tray_icon = tray_icon_ref # pystray.Icon object (passed from main, currently not used in HotkeyManager)
        self.audio_recorder = audio_recorder # This is our pre-warmed capable recorder

    def _play_start_beep_async(self):
        try:
            winsound.Beep(1000, 100) 
        except Exception as e:
            print(f"HotkeyManager: Error in _play_start_beep_async: {e}")

    def _on_press(self, key):
        if not self.app_state.listening_enabled or self.app_state.exit_requested:
            return True 

        is_left_ctrl = key == keyboard.Key.ctrl_l
        is_left_alt = key == keyboard.Key.alt_l
        
        if is_left_ctrl or is_left_alt: 
            self.currently_pressed_keys.add(key)

        if HOTKEY_COMBINATION_PRESS.issubset(self.currently_pressed_keys):
            if not self._hotkey_active_and_recording: 
                time_combo_confirmed = time.perf_counter()
                print(f"HotkeyManager: Ctrl+Alt PRESSED and HELD. (Combo confirmed at {time_combo_confirmed:.4f})")
                self._hotkey_active_and_recording = True
                
                # 1. Start "recording" (which is now just flipping a flag, should be very fast)
                time_before_start_recording = time.perf_counter()
                record_started_successfully = self.audio_recorder.start_recording()
                time_after_start_recording = time.perf_counter()
                print(f"DEBUG_TIMING: Actual 'start_recording' call took: {(time_after_start_recording - time_before_start_recording)*1000:.2f} ms")

                if record_started_successfully:
                    # 2. Play beep (asynchronously) to signal actual data capture has begun
                    beep_thread = threading.Thread(target=self._play_start_beep_async)
                    beep_thread.daemon = True 
                    beep_thread.start()
                    
                    self.app_state.set_recording(True) # Update global state

                    # 3. Get active window (can still be here, relatively fast)
                    try:
                        active_window = pyautogui.getActiveWindow()
                        title = active_window.title if active_window else None
                        self.app_state.set_active_window(title)
                        print(f"HotkeyManager: Active window on press: '{title}'")
                    except Exception as e:
                        print(f"HotkeyManager: Error getting active window: {e}")
                        self.app_state.set_active_window(None)
                else:
                    print("HotkeyManager: Failed to start audio recording process.")
                    self.app_state.update_status("Error: Failed to start recording.", is_recording=False)
                    self._hotkey_active_and_recording = False # Reset if failed to start
        return True

    def _on_release(self, key):
        if self.app_state.exit_requested:
            return False 

        original_hotkey_active_and_recording = self._hotkey_active_and_recording

        if key in self.currently_pressed_keys:
            self.currently_pressed_keys.remove(key)
            # print(f"HotkeyManager: Released {key}. Currently pressed: {self.currently_pressed_keys}") # Can be noisy

        # Only process release if we were actively recording due to hotkey
        # and one of the main hotkey components is released
        if key in HOTKEY_PARTIAL_RELEASE and original_hotkey_active_and_recording:
            # Check if the defining combination is truly broken (e.g. if alt OR ctrl is lifted from a ctrl+alt combo)
            # For simplicity, any monitored key release while active triggers stop.
            print(f"HotkeyManager: Monitored key {key} RELEASED while recording was active.")
            
            self.app_state.set_recording(False) # is_recording=False, status="Processing..."
            
            audio_file = self.audio_recorder.stop_recording() # Stops frame collection & saves
            self._hotkey_active_and_recording = False # Reset for next hotkey press cycle
            
            active_window_title_for_typing = self.app_state.active_window_title_on_press
            self.app_state.set_active_window(None) # Clear it after use

            final_status_message = "Error: Audio processing failed (no file)." # Default status

            if audio_file:
                self.app_state.update_status(f"Transcribing {os.path.basename(audio_file)}...", is_recording=False)
                transcribed_text = transcribe_audio_file(audio_file) # This can be an error string or actual text

                # Clean up temporary audio file
                try:
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                        print(f"HotkeyManager: Deleted temporary audio file: {audio_file}")
                except Exception as e_del:
                    print(f"HotkeyManager ERROR: Could not delete temp audio file {audio_file}: {e_del}")

                if transcribed_text and not transcribed_text.lower().startswith("error:"):
                    text_to_type = transcribed_text.strip()
                    if text_to_type: 
                        text_to_type_with_space = text_to_type + " " 
                        self.app_state.update_status(f"Typing: '{text_to_type[:30].strip()}...'")
                        time.sleep(0.1) 
                        insertion_success = insert_text_at_cursor(text_to_type_with_space, active_window_title_for_typing)
                        if insertion_success:
                            final_status_message = "Text inserted."
                        else:
                            final_status_message = "Error inserting text."
                    else: # Transcribed text was empty after strip
                        final_status_message = "Transcription was empty."
                else: # Transcription itself failed or returned an error string
                    final_status_message = transcribed_text if transcribed_text else "Transcription failed: Unknown error."
                
            self.app_state.update_status(final_status_message, is_recording=False) # Single final status update for this cycle
            
            self.currently_pressed_keys.clear() # Fully reset for next press combo
        return True

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

    def start(self): # Called when app starts or "Enable Hotkeys" is checked
        if self.listener_thread and self.listener_thread.is_alive():
            print("HotkeyManager: Listener already running.")
            # Ensure stream is open if listening is re-enabled
            if not self.audio_recorder._stream_is_open: # Accessing internal flag, better to have a public property or handle in open_stream
                print("HotkeyManager: Audio stream was closed, reopening...")
                self.audio_recorder.open_stream()
            return
        
        self.app_state.exit_requested = False 
        self.currently_pressed_keys.clear()
        self._hotkey_active_and_recording = False
        
        print("HotkeyManager: Opening audio stream for pre-warming...")
        if not self.audio_recorder.open_stream(): # Open stream when starting listener
            self.app_state.update_status("Error: Mic stream failed to open.", is_recording=False)
            return # Don't start listener if stream fails

        self.listener_thread = threading.Thread(target=self.run_listener, daemon=True)
        self.listener_thread.start()

    def stop(self): # Called on exit or when "Enable Hotkeys" is unchecked
        print("HotkeyManager: Stop requested.")
        self.app_state.exit_requested = True 
        if self.pynput_listener:
            try: self.pynput_listener.stop()
            except Exception as e: print(f"HotkeyManager: Error stopping pynput listener: {e}")
        
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=1.0)
        
        print("HotkeyManager: Closing audio stream...")
        self.audio_recorder.close_stream() # Close stream when stopping
        print("HotkeyManager: Stopped.")