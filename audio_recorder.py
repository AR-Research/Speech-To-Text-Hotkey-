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
        self._is_recording_active = False
        self._stream = None
        self._device_index = None

        try:
            default_mic = sd.query_devices(kind='input')
            # query_devices can return a list (multiple devices) or a dict (single default)
            selected_device = None
            if isinstance(default_mic, dict):
                selected_device = default_mic
            elif isinstance(default_mic, list) and default_mic:
                selected_device = default_mic[0] # Use the first one if multiple
            
            if selected_device:
                 self._device_index = selected_device.get('index')
                 print(f"AudioRecorder: Using microphone: {selected_device.get('name', 'Unknown Mic')} (Index: {self._device_index})")
            else:
                print("AudioRecorder WARNING: No default input microphone found or unexpected device format. Recording might fail.")
        except Exception as e:
            print(f"AudioRecorder ERROR: Could not query audio devices: {e}")


    def _callback(self, indata, frame_count, time_info, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            # sd.CallbackFlags(status).input_underflow etc. can be checked here
            print(f"AudioRecorder Callback Status: {status}") 
        if self._is_recording_active:
            self._frames.append(indata.copy())

    def start_recording(self):
        if self._is_recording_active:
            print("AudioRecorder: Already recording.")
            return True
        if self._device_index is None:
            print("AudioRecorder ERROR: No microphone device index configured. Cannot start recording.")
            return False

        print("AudioRecorder: Starting recording...")
        self._frames = [] # Reset frames for new recording
        try:
            self._stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                callback=self._callback,
                device=self._device_index,
                dtype='float32' # Explicitly request float32, common for sounddevice
            )
            self._is_recording_active = True
            self._stream.start()
            print("AudioRecorder: Recording stream started.")
            return True
        except Exception as e:
            print(f"AudioRecorder ERROR starting recording: {e}")
            self._is_recording_active = False
            if self._stream:
                try: self._stream.close()
                except Exception as e_close: print(f"AudioRecorder ERROR closing stream after failed start: {e_close}")
                self._stream = None
            return False

    def stop_recording(self) -> str | None:
        if not self._is_recording_active:
            print("AudioRecorder: Not recording or already stopped.")
            if self._frames: # Attempt to save any residual frames if stopped unexpectedly
                 print("AudioRecorder: Attempting to save residual frames from a non-active recording.")
            else:
                return None 

        print("AudioRecorder: Stopping recording...")
        self._is_recording_active = False 

        if self._stream:
            try:
                if self._stream.active: # Check if stream is active before stopping
                    self._stream.stop()
                self._stream.close()
                print("AudioRecorder: Recording stream stopped and closed.")
            except Exception as e:
                print(f"AudioRecorder ERROR stopping/closing stream: {e}")
            finally:
                self._stream = None
        else:
            print("AudioRecorder: Stream was already None when stop_recording called (or recording not started properly).")

        if not self._frames:
            print("AudioRecorder: No audio frames were captured.")
            return None

        try:
            recording_data = np.concatenate(self._frames, axis=0) # Likely float32 from sounddevice
            
            # Ensure data is clipped to [-1.0, 1.0] if it's float, then scale to int16
            if recording_data.dtype in (np.float32, np.float64):
                print(f"AudioRecorder: Converting {recording_data.dtype} audio data to int16 PCM.")
                recording_data_clipped = np.clip(recording_data, -1.0, 1.0)
                data_to_write = np.int16(recording_data_clipped * 32767)
            elif recording_data.dtype == np.int16:
                print("AudioRecorder: Audio data is already int16.")
                data_to_write = recording_data
            else:
                print(f"AudioRecorder WARNING: Unexpected audio data type: {recording_data.dtype}. Attempting conversion to int16.")
                # Attempt a generic conversion, this might fail or produce poor results
                recording_data_clipped = np.clip(recording_data.astype(np.float32), -1.0, 1.0)
                data_to_write = np.int16(recording_data_clipped * 32767)

            wav.write(self.temp_filename, self.samplerate, data_to_write)
            print(f"AudioRecorder: Recording (as int16 PCM) saved to {self.temp_filename}")
            self._frames = [] 
            return self.temp_filename
        except ValueError as ve:
            print(f"AudioRecorder ERROR: ValueError saving .wav file (maybe no data after processing?): {ve}")
        except Exception as e:
            print(f"AudioRecorder ERROR saving .wav file: {e}")
        
        self._frames = [] 
        return None