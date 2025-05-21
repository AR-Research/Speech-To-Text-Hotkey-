# audio_recorder.py
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import threading 
import time 

class AudioRecorder:
    def __init__(self, temp_filename="temp_audio.wav", samplerate=44100, channels=1):
        self.temp_filename = temp_filename
        self.samplerate = samplerate
        self.channels = channels
        self._frames = []
        self._is_actively_saving_frames = False # Flag to control saving in callback
        self._stream_is_open = False
        self._stream: sd.InputStream | None = None # Type hint for clarity
        self._device_index = None
        self._lock = threading.Lock() # To protect access to _frames and flags

        try:
            default_mic = sd.query_devices(kind='input')
            selected_device = None
            if isinstance(default_mic, dict): selected_device = default_mic
            elif isinstance(default_mic, list) and default_mic: selected_device = default_mic[0]
            
            if selected_device:
                 self._device_index = selected_device.get('index')
                 print(f"AudioRecorder: Default microphone: {selected_device.get('name', 'Unknown Mic')} (Index: {self._device_index})")
            else:
                print("AudioRecorder WARNING: No default input microphone found.")
        except Exception as e:
            print(f"AudioRecorder ERROR: Could not query audio devices: {e}")

    def _callback(self, indata, frame_count, time_info, status):
        if status: print(f"AudioRecorder Callback Status: {status}")
        with self._lock:
            if self._is_actively_saving_frames:
                self._frames.append(indata.copy())

    def open_stream(self):
        with self._lock:
            if self._stream_is_open:
                print("AudioRecorder: Stream already open.")
                return True
            if self._device_index is None:
                print("AudioRecorder ERROR: No microphone device index. Cannot open stream.")
                return False
            try:
                print("AudioRecorder: Opening audio stream...")
                self._stream = sd.InputStream(
                    samplerate=self.samplerate,
                    channels=self.channels,
                    callback=self._callback,
                    device=self._device_index,
                    dtype='float32'
                )
                self._stream.start() # Start delivering data to callback immediately
                self._stream_is_open = True
                print("AudioRecorder: Audio stream opened and started.")
                return True
            except Exception as e:
                print(f"AudioRecorder ERROR opening stream: {e}")
                self._stream = None
                self._stream_is_open = False
                return False

    def close_stream(self):
        with self._lock:
            if not self._stream_is_open or not self._stream:
                print("AudioRecorder: Stream already closed or never opened.")
                return True
            print("AudioRecorder: Closing audio stream...")
            try:
                self._is_actively_saving_frames = False # Ensure no more frames are saved
                self._stream.stop()
                self._stream.close()
                print("AudioRecorder: Audio stream stopped and closed.")
            except Exception as e:
                print(f"AudioRecorder ERROR closing stream: {e}")
            finally:
                self._stream = None
                self._stream_is_open = False
            return True

    def start_recording(self): # This is now very fast
        with self._lock:
            if not self._stream_is_open:
                print("AudioRecorder: Stream not open. Attempting to open...")
                if not self.open_stream(): # Try to open it if not already
                    print("AudioRecorder ERROR: Failed to open stream for recording.")
                    return False # Failed to start
            
            if self._is_actively_saving_frames: # Already "recording" (saving frames)
                print("AudioRecorder: Already actively saving frames.")
                return True

            print("AudioRecorder: Starting to save frames (recording effectively begins).")
            self._frames = [] # Clear any old frames
            self._is_actively_saving_frames = True
        return True

    def stop_recording(self) -> str | None: # This is also fast for stopping frame capture
        print("AudioRecorder: Stopping frame capture...")
        saved_file_path = None
        with self._lock:
            if not self._is_actively_saving_frames and not self._frames: # Not saving and no frames = nothing to do
                print("AudioRecorder: Not actively saving frames and no frames to process.")
                # Optionally, if you want to keep the stream open for next recording:
                # return None 
                # If you want to close stream after every recording (less "warm"):
                # self.close_stream() 
                return None

            self._is_actively_saving_frames = False # Signal callback to stop appending

            if not self._frames:
                print("AudioRecorder: No audio frames were captured to save.")
                return None
            
            # Save accumulated frames
            try:
                # This part can still take a moment (file I/O)
                # but the critical data capture has stopped immediately.
                recording_data = np.concatenate(self._frames, axis=0)
                recording_data_clipped = np.clip(recording_data, -1.0, 1.0)
                data_to_write = np.int16(recording_data_clipped * 32767)
                
                wav.write(self.temp_filename, self.samplerate, data_to_write)
                print(f"AudioRecorder: Recording (as int16 PCM) saved to {self.temp_filename}")
                saved_file_path = self.temp_filename
            except ValueError as ve:
                print(f"AudioRecorder ERROR: ValueError saving .wav file: {ve}")
            except Exception as e:
                print(f"AudioRecorder ERROR saving .wav file: {e}")
            finally:
                self._frames = [] # Clear frames after attempting to save

        # Decide if you want to close the stream here or keep it open
        # For "hot" mic, keep it open. For explicit close after each use:
        # self.close_stream()
        return saved_file_path