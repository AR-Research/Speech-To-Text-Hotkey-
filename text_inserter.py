# text_inserter.py
import pyautogui
import time

def insert_text_at_cursor(text_to_insert: str, target_window_title: str | None = None):
    """
    Types the given text into the currently focused UI element.
    Attempts to refocus the target_window_title if provided.
    """
    if not text_to_insert or text_to_insert.lower().startswith("error:"):
        print(f"TextInserter: Invalid text or error received, not typing: '{text_to_insert}'")
        return False

    print(f"TextInserter: Attempting to type: '{text_to_insert}'")
    
    try:
        # Attempt to refocus the original window if a title was captured
        if target_window_title:
            print(f"TextInserter: Attempting to focus window: '{target_window_title}'")
            try:
                windows = pyautogui.getWindowsWithTitle(target_window_title)
                if windows:
                    target_window = windows[0]
                    # Check if already active to avoid unnecessary switching
                    current_active_window = pyautogui.getActiveWindow()
                    if current_active_window is None or current_active_window.title != target_window.title:
                        # Simple activation; more robust might need OS-specific calls
                        if target_window.isMinimized: target_window.restore()
                        if not target_window.isActive: target_window.activate()
                        time.sleep(0.3) # Give OS time to switch focus
                        # Verify focus (optional)
                        # current_active_window = pyautogui.getActiveWindow()
                        # if current_active_window and current_active_window.title == target_window.title:
                        # print(f"TextInserter: Successfully focused window: '{target_window.title}'")
                        # else:
                        # print(f"TextInserter: Failed to confirm focus on '{target_window.title}'. Typing into current active field.")
                    else:
                        print(f"TextInserter: Target window '{target_window.title}' already active.")
                else:
                    print(f"TextInserter: Could not find window with title: '{target_window_title}'. Typing into current active field.")
                    time.sleep(0.2) # Small delay just in case
            except Exception as e:
                print(f"TextInserter: Error trying to activate window '{target_window_title}': {e}. Typing into current active field.")
                time.sleep(0.2)
        else:
            print("TextInserter: No specific target window title provided. Typing into current active field.")
            time.sleep(0.2) # Small delay for focus

        pyautogui.typewrite(text_to_insert, interval=0.01)
        print("TextInserter: Text typed successfully.")
        return True
    except Exception as e:
        print(f"TextInserter ERROR: Could not type text: {e}")
        return False