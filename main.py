# main.py
import sys
import threading
import time
import os # For path operations if needed by STT or audio_recorder
from PIL import Image, ImageDraw
from pystray import Icon as PystrayIcon, Menu as PystrayMenu, MenuItem as PystrayMenuItem

from app_state import AppState
from audio_recorder import AudioRecorder
from hotkey_manager import HotkeyManager
# STT and TextInserter are used by HotkeyManager, no direct import needed here unless for other purposes

# --- Globals ---
app_state_instance = AppState()
global_pystray_icon = None # Will hold the pystray.Icon object
audio_recorder_instance = AudioRecorder(temp_filename="temp_voice_input.wav") # Can customize filename
hotkey_manager_instance = None # Will be initialized in main

# --- System Tray Icon Update Function ---
# This will be run in a separate thread to periodically update the icon/tooltip
# based on shared AppState.
def tray_icon_updater(icon: PystrayIcon, app_state: AppState):
    """Periodically updates the tray icon and tooltip based on AppState."""
    last_shown_recording_state = app_state.is_recording
    last_shown_status_message = app_state.status_message
    last_listening_enabled_state = app_state.listening_enabled

    # Initial state set before loop (optional, as the loop will set it)
    # current_status_for_icon = "idle"
    # if not app_state.listening_enabled: current_status_for_icon = "disabled"
    # # ... more initial logic if desired, or let the loop handle it on first run ...
    # icon.icon = get_icon_for_state(current_status_for_icon)
    # icon.title = f"Voice-to-Text: {app_state.status_message}"


    while not app_state.exit_requested:
        # It's better to lock when reading multiple related attributes from app_state
        # to ensure a consistent snapshot, though for simple flags it might be overkill.
        # For simplicity, we'll read them and if they change, then lock for update if needed.
        
        current_is_recording = app_state.is_recording
        current_status_msg = app_state.status_message
        current_listening_enabled = app_state.listening_enabled

        recording_changed = current_is_recording != last_shown_recording_state
        status_changed = current_status_msg != last_shown_status_message
        listening_changed = current_listening_enabled != last_listening_enabled_state

        if recording_changed or status_changed or listening_changed:
            last_shown_recording_state = current_is_recording
            last_shown_status_message = current_status_msg
            last_listening_enabled_state = current_listening_enabled

            current_status_for_icon = "idle" # Default if listening
            if not current_listening_enabled:
                current_status_for_icon = "disabled"
            elif current_is_recording:
                current_status_for_icon = "recording"
            elif "processing" in current_status_msg.lower(): 
                current_status_for_icon = "processing"
            elif "error" in current_status_msg.lower(): 
                current_status_for_icon = "error_generic" 
            
            new_icon_image = get_icon_for_state(current_status_for_icon)
            if icon.icon != new_icon_image : 
                icon.icon = new_icon_image
            
            # --- Truncation logic for tooltip ---
            tooltip_prefix = "Voice-to-Text: "
            # Windows tooltip length limit is around 127 characters for the text itself.
            # Let's aim for max_tooltip_len = 127 for the entire string.
            max_tooltip_len = 127 
            max_status_message_len = max_tooltip_len - len(tooltip_prefix)

            status_for_tooltip = current_status_msg
            if len(current_status_msg) > max_status_message_len:
                status_for_tooltip = current_status_msg[:max_status_message_len - 3] + "..."
            
            new_title = f"{tooltip_prefix}{status_for_tooltip}"
            # --- End of truncation logic ---
            
            if icon.title != new_title:
                icon.title = new_title # This is the line that raised the error
            
            print(f"TRAY_UPDATE: Icon: {current_status_for_icon}, Title: '{new_title}' (Original status: '{current_status_msg}')")

        time.sleep(0.2) # Update frequency for tray icon/tooltip
    print("Tray icon updater thread exiting.")


# --- System Tray Icon Image Generation (keep as is) ---
def create_dummy_icon(size=(64, 64), color1='blue', color2='lightblue', shape='ellipse'):
    image = Image.new('RGBA', size, (0, 0, 0, 0)) 
    dc = ImageDraw.Draw(image)
    if shape == 'ellipse': dc.ellipse([(5, 5), (size[0]-5, size[1]-5)], fill=color1, outline=color2)
    else: dc.rectangle([(5, 5), (size[0]-5, size[1]-5)], fill=color1, outline=color2)
    return image

def get_icon_for_state(state: str): # state can be "idle", "recording", "processing", "disabled", "error_generic"
    print(f"ICON_STATE_REQUEST: '{state}'")
    if state == "recording": return create_dummy_icon(color1='red', color2='pink', shape='ellipse')
    elif state == "processing": return create_dummy_icon(color1='yellow', color2='lightyellow', shape='ellipse')
    elif state == "disabled": return create_dummy_icon(color1='grey', color2='lightgrey', shape='rect')
    elif state.startswith("error"): return create_dummy_icon(color1='orange', color2="#FF4500", shape='rect') # Darker orange for error
    else: return create_dummy_icon(color1='blue', color2='lightblue', shape='ellipse') # idle

# --- System Tray Menu Callbacks ---
def on_toggle_listening(icon, item): # Tray menu callback
    with app_state_instance.lock:
        app_state_instance.listening_enabled = not app_state_instance.listening_enabled
        if app_state_instance.listening_enabled:
            app_state_instance.status_message = "Idle - Listening"
            hotkey_manager_instance.start() # This will open/ensure audio stream is open
        else:
            app_state_instance.status_message = "Idle - Not Listening"
            hotkey_manager_instance.stop() # This will stop listener AND close audio stream
    print(f"System Tray: Listening toggled to {app_state_instance.listening_enabled}")

def on_exit_app(icon_obj, item): # Tray menu callback
    print("System Tray: Exit requested by user.")
    app_state_instance.update_status("Exiting...", is_recording=False)
    app_state_instance.exit_requested = True # Signals all threads
    app_state_instance.listening_enabled = False 
    
    if hotkey_manager_instance:
        hotkey_manager_instance.stop() # This will also close the audio stream
    
    if global_pystray_icon: 
        global_pystray_icon.stop()
    print("Main: pystray icon stop called.")

# --- Main Application ---
# --- Main Application ---
if __name__ == "__main__":
    print("Starting Background Voice-to-Text Application (Simplified Version)...")

    # Initialize components
    # app_state_instance is already global
    # audio_recorder_instance is already global (or defined here if preferred)
    if 'audio_recorder_instance' not in globals(): # Ensure it's defined if not already global
        audio_recorder_instance = AudioRecorder(temp_filename="temp_voice_input.wav")
    
    hotkey_manager_instance = HotkeyManager(app_state_instance, audio_recorder_instance)

    # --- Define the menu FIRST ---
    menu = PystrayMenu(
        PystrayMenuItem(
            'Enable Hotkeys', 
            on_toggle_listening,
            checked=lambda item: app_state_instance.listening_enabled, # Dynamic check
            radio=True # Makes it look like a toggle
        ),
        PystrayMenu.SEPARATOR,
        PystrayMenuItem('Exit Application', on_exit_app)
    )

    # --- THEN create the icon using the defined menu ---
    initial_icon_image = get_icon_for_state("idle") 
    if not app_state_instance.listening_enabled: # Check initial state for icon
        initial_icon_image = get_icon_for_state("disabled")
        
    global_pystray_icon = PystrayIcon(
        "Voice2Text Simplified", 
        initial_icon_image, 
        "Voice-to-Text: Initializing...", # Initial tooltip
        menu  # Now 'menu' is defined
    )
    
    # Start the hotkey listener thread 
    if app_state_instance.listening_enabled:
        hotkey_manager_instance.start() 
    else: 
        # audio_recorder_instance.close_stream() # This might be too aggressive if HKM manages it
        app_state_instance.status_message = "Idle - Not Listening (Hotkeys Disabled)"

    tray_updater_thread = threading.Thread(
        target=tray_icon_updater, 
        args=(global_pystray_icon, app_state_instance), 
        daemon=True
    )
    tray_updater_thread.start()
    
    print("System Tray Icon and Hotkey Manager configured. Application running...")
    # Set initial status message after HKM start might have opened stream
    if app_state_instance.listening_enabled:
        app_state_instance.update_status("Idle - Listening")
    else:
        app_state_instance.update_status("Idle - Not Listening (Hotkeys Disabled)")


    try:
        global_pystray_icon.run() 
    except KeyboardInterrupt:
        print("\nMain: KeyboardInterrupt received. Shutting down.")
        on_exit_app(None, None) 
    except Exception as e:
        print(f"Main: An error occurred with pystray: {e}")
        import traceback
        traceback.print_exc()
        on_exit_app(None, None) 
    finally:
        print("Application shutting down...")
        if not app_state_instance.exit_requested: 
            app_state_instance.exit_requested = True
            app_state_instance.listening_enabled = False
            if hotkey_manager_instance:
                hotkey_manager_instance.stop()
        
        if hasattr(hotkey_manager_instance, 'listener_thread') and hotkey_manager_instance.listener_thread and hotkey_manager_instance.listener_thread.is_alive():
            print("Main: Waiting for HotkeyManager thread to join...")
            hotkey_manager_instance.listener_thread.join(timeout=2.0)
            if hotkey_manager_instance.listener_thread.is_alive():
                print("Main WARN: HotkeyManager thread did not join in time.")
        
        if tray_updater_thread.is_alive(): # tray_updater_thread is defined inside __main__
            print("Main: Waiting for tray_updater_thread to join...")
            tray_updater_thread.join(timeout=1.0) 
            if tray_updater_thread.is_alive():
                 print("Main WARN: Tray updater thread did not join in time.")

        print("Main: Application exited.")