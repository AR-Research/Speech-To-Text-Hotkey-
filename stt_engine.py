# stt_engine.py
import speech_recognition as sr
import os

def transcribe_audio_file(audio_file_path: str) -> str | None:
    """
    Transcribes an audio file using Google Web Speech API.
    Returns the transcribed text or an error string.
    """
    if not audio_file_path or not os.path.exists(audio_file_path):
        print(f"STT Engine ERROR: Audio file not found or path is invalid: '{audio_file_path}'")
        return f"Error: Audio file not found at '{audio_file_path}'"
    if os.path.getsize(audio_file_path) < 44: # WAV header size
        print(f"STT Engine ERROR: Audio file '{audio_file_path}' appears to be empty or invalid WAV.")
        return "Error: Audio file is empty or invalid."

    recognizer = sr.Recognizer()
    print(f"STT Engine: Attempting to transcribe '{audio_file_path}' using Google Web Speech API...")
    
    with sr.AudioFile(audio_file_path) as source:
        try:
            audio_data = recognizer.record(source)
        except ValueError:
            print(f"STT Engine ERROR: ValueError recording from audio file '{audio_file_path}' (likely empty or corrupt).")
            return "Error: Could not process audio file (empty/corrupt)."
        except Exception as e:
            print(f"STT Engine ERROR: Failed to record audio from file '{audio_file_path}': {e}")
            return f"Error reading audio file: {e}"

    try:
        # Use Google Web Speech API for transcription
        text = recognizer.recognize_google(audio_data)
        print(f"STT Engine (Google): Transcription: '{text}'")
        return text
    except sr.UnknownValueError:
        print("STT Engine (Google) ERROR: Google Web Speech API could not understand audio.")
        return "Error: Unable to transcribe audio (speech not understood)."
    except sr.RequestError as e:
        print(f"STT Engine (Google) ERROR: Could not request results from Google Web Speech API; {e}")
        return f"Error: Google Web Speech API request failed ({e}). Check internet connection."
    except Exception as e:
        print(f"STT Engine (Google) ERROR: Unexpected error during transcription: {e}")
        return f"Error: Transcription failed unexpectedly ({e})."