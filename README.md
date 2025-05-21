# Background Voice-to-Text Utility for Windows

This Python application runs discreetly in the background on your Windows system. It listens for a global hotkey combination (`Ctrl + Alt`). When these keys are pressed and held, it records audio from your microphone. Upon release, it converts the audio to text (using an offline engine by default) and automatically types this text into the UI element that currently has focus (e.g., a search bar, text editor, form field).

This version is a direct Python implementation focused on speed and efficiency, without the CrewAI framework.

## Core Features

-   **Background Operation**: Runs unobtrusively.
-   **System Tray Icon**: Provides basic controls:
    -   "Enable Hotkeys" / "Disable Hotkeys": Toggles hotkey detection.
    -   "Exit Application": Shuts down the application.
    -   Icon changes to indicate status (idle, recording, processing, error).
    -   Tooltip shows current status.
-   **Global Hotkey Activation**:
    -   `Ctrl + Alt` (Left Ctrl + Left Alt by default) press and hold: Starts audio recording.
    -   Release of `Ctrl` or `Alt`: Stops recording, initiates transcription, and types out the text.
-   **Audio Recording**: Captures audio from the system's default microphone.
-   **Offline Speech-to-Text (STT)**: Uses CMU Sphinx via the `SpeechRecognition` library by default for fast, private, offline transcription.
-   **Text Output**: Simulates keyboard input to type the transcribed text into the active application's focused field.

## Setup Instructions

### 1. Python
Ensure you have Python 3.8 or newer installed. Python 3.10+ is recommended.

### 2. Create a Virtual Environment (Recommended)
```bash
python -m venv .venv
# On Windows
.\.venv\Scripts\activate
# On macOS/Linux
# source .venv/bin/activate