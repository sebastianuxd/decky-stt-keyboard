import logging
import os
import sys
import subprocess
import asyncio
import json
import threading
import time
from collections import deque
from pathlib import Path

# The decky plugin module is located at decky-loader/plugin
# For the hosted code: `import decky` works, but the actual source is in decky-loader/plugin/decky.py
import decky
try:
    import decky_plugin
except ImportError:
    decky_plugin = None
import ssl

# Create unverified SSL context for model download
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="[STT Keyboard] %(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger()

# Get the plugin directory
PLUGIN_DIR = Path(decky.DECKY_PLUGIN_DIR)
# Use a user-writable directory for data and dependencies
# This avoids permission issues when the plugin directory is owned by root
DATA_DIR = Path(os.environ.get("HOME", "/home/deck")) / ".local/share/decky-stt-keyboard"
# We now bundle dependencies in the plugin directory itself to avoid installation issues
BUNDLED_LIB_DIR = PLUGIN_DIR / "lib"
MODEL_DIR = DATA_DIR / "models"
REQUIREMENTS_FILE = PLUGIN_DIR / "requirements.txt"
# Whisper model configuration
WHISPER_MODEL_NAME = "tiny"  # Options: tiny, base, small, medium, large
WHISPER_MODEL_PATH = MODEL_DIR / "whisper-tiny"


class Plugin:
    """
    STT Keyboard Backend Plugin
    
    Handles offline speech recognition using Whisper and sounddevice
    for microphone access without browser permission issues.
    """

    def __init__(self):
        self.settings = {}
        self.whisper_model = None
        self.audio_buffer = []  # Buffer for audio data during recording
        self.audio_stream = None
        self.is_recording = False
        self.recording_thread = None
        self.loop = None
        # Queue for storing transcription results for polling
        self.transcription_queue = deque(maxlen=100)

    @staticmethod
    def play_sound():
        """Play the start listening sound"""
        # Try multiple sound files in order of preference
        sound_paths = [
            "/usr/share/sounds/freedesktop/stereo/bell.oga",
            "/usr/share/sounds/freedesktop/stereo/message.oga",
            "/usr/share/sounds/freedesktop/stereo/service-login.oga",
            "/usr/share/sounds/freedesktop/stereo/complete.oga",
        ]
        
        for sound_path in sound_paths:
            if os.path.exists(sound_path):
                logger.info(f"Attempting to play sound: {sound_path}")
                try:
                    # Use paplay with explicit output device to ensure it goes to default sink
                    result = subprocess.run(
                        ["paplay", sound_path],
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        timeout=3  # 3 second timeout
                    )
                    if result.returncode == 0:
                        logger.info(f"Successfully played sound: {sound_path}")
                        return
                    else:
                        logger.warning(f"paplay returned {result.returncode} for {sound_path}: {result.stderr.decode()}")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Sound playback timed out for {sound_path}")
                except Exception as e:
                    logger.warning(f"paplay failed for {sound_path}: {e}")
        
        logger.error("All sound playback attempts failed")

    def emit_event(self, event_name: str, data: dict):
        """Emit an event to the frontend"""
        try:
            if self.loop and self.loop.is_running():
                # Handle static context for emit_event which calls _emit_async
                # _emit_async expects (self, event_name, data)
                # If self is class, we must call calling it explicitly or ensuring self is bound?
                # Actually, if self is class, self._emit_async is UNBOUND: Plugin._emit_async
                # So we must call Plugin._emit_async(self, event_name, data)
                if isinstance(self, type):
                   asyncio.run_coroutine_threadsafe(Plugin._emit_async(self, event_name, data), self.loop)
                else:
                   asyncio.run_coroutine_threadsafe(self._emit_async(event_name, data), self.loop)
            else:
                logger.warning(f"Event loop not ready, cannot emit {event_name}")
        except Exception as e:
            logger.error(f"Failed to emit event {event_name}: {e}")

    async def _emit_async(self, event_name: str, data: dict):
        try:
            # Try to use self.emit (Decky Plugin API)
            # Try to use self.emit (Decky Plugin API)
            if hasattr(self, "emit"):
                await self.emit(event_name, data)
            elif decky_plugin and hasattr(decky_plugin, "emit"):
                decky_plugin.emit(event_name, data)
            elif hasattr(decky, "emit"):
                # Fallback to decky module
                decky.emit(event_name, data)
            else:
                logger.error(f"No emit method available for event {event_name}")

        except Exception as e:
            logger.error(f"Error in _emit_async for {event_name}: {e}")

    async def _main(self):
        logger.info("=" * 60)
        logger.info(f"STT KEYBOARD PLUGIN: _main() CALLED - STARTING INITIALIZATION. self type: {type(self)}")
        
        # Initialize attributes if running as class (static context)
        if isinstance(self, type):
            logger.info("Running in static context - initializing class attributes")
            if not hasattr(self, "settings"): self.settings = {}
            if not hasattr(self, "whisper_model"): self.whisper_model = None
            if not hasattr(self, "audio_buffer"): self.audio_buffer = []
            if not hasattr(self, "audio_stream"): self.audio_stream = None
            if not hasattr(self, "is_recording"): self.is_recording = False
            if not hasattr(self, "recording_thread"): self.recording_thread = None
            if not hasattr(self, "loop"): self.loop = None

        import os
        import pwd
        import inspect
        try:
            uid = os.getuid()
            user = pwd.getpwuid(uid).pw_name
            logger.info(f"Running as user: {user} (uid: {uid})")
            logger.info(f"Plugin directory: {PLUGIN_DIR}")
            if PLUGIN_DIR.exists():
                stat = os.stat(PLUGIN_DIR)
                logger.info(f"Plugin directory permissions: {oct(stat.st_mode)}")
                logger.info(f"Plugin directory owner: {stat.st_uid}")
            else:
                logger.error(f"Plugin directory does not exist: {PLUGIN_DIR}")
            
            # Inspect _ensure_dependencies
            logger.info(f"Inspecting _ensure_dependencies...")
            try:
                sig = inspect.signature(self._ensure_dependencies)
                logger.info(f"_ensure_dependencies signature: {sig}")
                is_static = isinstance(inspect.getattr_static(Plugin, '_ensure_dependencies'), staticmethod)
                logger.info(f"_ensure_dependencies is staticmethod: {is_static}")
            except Exception as e:
                logger.error(f"Failed to inspect _ensure_dependencies: {e}")

        except Exception as e:
            logger.error(f"Failed to log environment info: {e}")
        logger.info("=" * 60)
        try:
            self.loop = asyncio.get_running_loop()
            if not hasattr(self, "settings"):
                self.settings = {}
            
            # Ensure data directory exists and is writable
            try:
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                if not os.access(DATA_DIR, os.W_OK):
                    logger.error(f"CRITICAL: Data directory {DATA_DIR} is not writable!")
            except Exception as e:
                logger.error(f"Error creating data directory {DATA_DIR}: {e}")

            # Ensure directories exist
            try:
                MODEL_DIR.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                logger.error(f"Permission denied creating {MODEL_DIR}. Please check directory permissions.")
            except Exception as e:
                logger.error(f"Error creating {MODEL_DIR}: {e}")

            # Check and install dependencies
            if not await self._ensure_dependencies():
                logger.error("Failed to ensure dependencies. Plugin functionality will be limited.")
            
            logger.info("STT Keyboard: Settings initialized successfully")
            logger.info("STT Keyboard: Plugin loaded successfully")
        except Exception as e:
            logger.error(f"STT Keyboard: Error during initialization: {e}", exc_info=True)
            raise

    async def _unload(self):
        logger.info(f"STT Keyboard plugin unloading. self type: {type(self)}")
        try:
            if isinstance(self, type):
                logger.info("Unloading in static context (self is class)")
                # If self is the class, we need to pass it explicitly to the unbound method
                await self.stop_stt(self)
            else:
                logger.info("Unloading in instance context")
                await self.stop_stt()
        except Exception as e:
            logger.error(f"Error in _unload: {e}", exc_info=True)
        logger.info("STT Keyboard plugin unloaded")

    @staticmethod
    async def _ensure_dependencies():
        """Ensure Python dependencies are available"""
        try:
            # Add bundled lib directory to Python path
            if BUNDLED_LIB_DIR.exists():
                if str(BUNDLED_LIB_DIR) not in sys.path:
                    sys.path.insert(0, str(BUNDLED_LIB_DIR))
                    logger.info(f"Added bundled lib directory to sys.path: {BUNDLED_LIB_DIR}")
            else:
                logger.error(f"Bundled lib directory not found: {BUNDLED_LIB_DIR}")
                return False

            # Check if dependencies are importable
            try:
                from faster_whisper import WhisperModel
                import sounddevice
                import numpy
                logger.info("All dependencies successfully imported (faster-whisper, sounddevice, numpy)")
                return True
            except ImportError as e:
                logger.error(f"Failed to import dependencies despite adding lib to path: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error ensuring dependencies: {e}", exc_info=True)
            return False

    async def get_model_status(self):
        """Check if the Whisper model is downloaded/cached"""
        # Whisper models are cached by huggingface_hub
        # Check if model directory exists with model files
        try:
            from huggingface_hub import scan_cache_dir
            cache_info = scan_cache_dir()
            # Look for any whisper model in cache
            for repo in cache_info.repos:
                if "whisper" in repo.repo_id.lower() and WHISPER_MODEL_NAME in repo.repo_id.lower():
                    logger.info(f"Found cached Whisper model: {repo.repo_id}")
                    return {
                        "downloaded": True,
                        "path": str(repo.repo_path),
                        "name": f"whisper-{WHISPER_MODEL_NAME}"
                    }
        except Exception as e:
            logger.warning(f"Error checking huggingface cache: {e}")
        
        # Also check if model is loaded
        if self.whisper_model is not None:
            return {
                "downloaded": True,
                "path": "loaded",
                "name": f"whisper-{WHISPER_MODEL_NAME}"
            }
        
        return {
            "downloaded": False,
            "path": "",
            "name": f"whisper-{WHISPER_MODEL_NAME}"
        }

    async def download_model(self):
        """Download the Whisper speech recognition model"""
        logger.info("=" * 60)
        logger.info("download_model() called - Whisper model")
        logger.info("=" * 60)
        try:
            # Ensure model directory exists
            if not MODEL_DIR.exists():
                try:
                    MODEL_DIR.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created model directory: {MODEL_DIR}")
                except Exception as e:
                    error_msg = f"Failed to create model directory: {e}"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}

            # Whisper models auto-download via huggingface_hub when first loaded
            # So we just need to load the model here
            logger.info(f"Downloading/loading Whisper model: {WHISPER_MODEL_NAME}")
            
            try:
                from faster_whisper import WhisperModel
                
                # This will download the model if not cached
                logger.info("Initializing WhisperModel (will download if needed)...")
                self.whisper_model = WhisperModel(
                    WHISPER_MODEL_NAME,
                    device="cpu",
                    compute_type="int8",  # Use int8 for better performance on CPU
                    download_root=str(MODEL_DIR)
                )
                
                logger.info("Whisper model loaded successfully")
                return {"success": True, "path": str(MODEL_DIR)}
                
            except Exception as load_error:
                logger.error(f"Failed to load Whisper model: {load_error}", exc_info=True)
                return {"success": False, "error": f"Model load failed: {load_error}"}
            
        except Exception as e:
            logger.error(f"Error downloading model: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def load_model(self):
        """Load the Whisper model into memory"""
        try:
            if self.whisper_model is not None:
                logger.info("Model already loaded")
                return {"success": True}
            
            from faster_whisper import WhisperModel
            
            logger.info(f"Loading Whisper model: {WHISPER_MODEL_NAME}")
            self.whisper_model = WhisperModel(
                WHISPER_MODEL_NAME,
                device="cpu",
                compute_type="int8",
                download_root=str(MODEL_DIR)
            )
            
            logger.info("Model loaded successfully")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error loading model: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream - buffers audio data for Whisper"""
        try:
            if status:
                logger.warning(f"Audio callback status: {status}")
            
            # Ensure audio_buffer exists
            if not hasattr(self, 'audio_buffer'):
                self.audio_buffer = []
            
            # Convert to numpy array for processing
            import numpy as np
            audio_array = np.frombuffer(bytes(indata), dtype=np.int16).copy()
            
            # Apply gain normalization (boost quiet audio)
            max_val = np.max(np.abs(audio_array))
            if max_val > 0:
                # Normalize to 80% of max range to avoid clipping
                target_level = 32767 * 0.8
                gain = min(target_level / max_val, 10.0)  # Cap gain at 10x
                if gain > 1.5:  # Only boost if audio is quiet
                    audio_array = (audio_array * gain).astype(np.int16)
            
            # Buffer the audio data
            self.audio_buffer.append(audio_array)
            
            # Log periodically
            if not hasattr(self, '_callback_count'):
                self._callback_count = 0
            self._callback_count += 1
            
            if self._callback_count == 1 or self._callback_count % 100 == 0:
                rms = np.sqrt(np.mean(audio_array.astype(float)**2))
                logger.info(f"Audio callback #{self._callback_count}: frames={frames}, RMS={rms:.1f}")
                    
        except Exception as e:
            logger.error(f"Error in audio callback: {e}", exc_info=True)

    async def start_stt(self, language: str = "en-US"):
        """Start speech-to-text recording"""
        logger.info("=" * 60)
        logger.info(f"start_stt() CALLED with language={language}")
        logger.info(f"self type: {type(self)}, is_recording: {getattr(self, 'is_recording', 'UNDEFINED')}")
        logger.info("=" * 60)
        try:
            if self.is_recording:
                logger.warning("STT already recording")
                return {"success": False, "error": "Already recording"}
            
            # Ensure model is loaded
            if self.whisper_model is None:
                if isinstance(self, type):
                    load_result = await Plugin.load_model(self)
                else:
                    load_result = await self.load_model()
                if not load_result["success"]:
                    return load_result
            
            import sounddevice as sd
            import numpy as np
            
            # Clear audio buffer
            self.audio_buffer = []
            self._callback_count = 0
            
            # Start audio stream
            logger.info("Starting audio recording for Whisper...")
            
            # Query default input device
            try:
                device_info = sd.query_devices(kind='input')
                if device_info:
                    self.sample_rate = int(device_info['default_samplerate'])
                    logger.info(f"Detected Input Device: {device_info['name']}, Rate: {self.sample_rate}")
                else:
                    self.sample_rate = 16000
                    logger.warning("Could not detect input device, using 16000 Hz")
            except Exception as e:
                logger.error(f"Error querying devices: {e}")
                self.sample_rate = 16000

            # Play start sound
            self.play_sound()

            # Create callback wrapper
            plugin_self = self
            def audio_callback_wrapper(indata, frames, time_info, status):
                if isinstance(plugin_self, type):
                    Plugin._audio_callback(plugin_self, indata, frames, time_info, status)
                else:
                    plugin_self._audio_callback(indata, frames, time_info, status)
            
            logger.info("Creating audio stream...")

            # Open audio stream - Whisper works best with 16kHz but we'll resample if needed
            self.audio_stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=4000,
                dtype='int16',
                channels=1,
                callback=audio_callback_wrapper
            )
            
            self.audio_stream.start()
            self.is_recording = True
            
            logger.info("STT recording started - speak now, transcription happens when you stop")
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error starting STT: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def stop_stt(self):
        """Stop speech-to-text recording and transcribe with Whisper"""
        logger.info(f"stop_stt called. self type: {type(self)}")
        try:
            if isinstance(self, type):
                is_recording = getattr(self, "is_recording", False)
            else:
                is_recording = self.is_recording

            if not is_recording:
                logger.info("stop_stt: Not recording, nothing to stop")
                return {"success": True}
            
            logger.info("Stopping STT recording...")
            
            # Stop audio stream
            if self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream.close()
                self.audio_stream = None
            
            self.is_recording = False
            
            # Get buffered audio
            if not hasattr(self, 'audio_buffer') or not self.audio_buffer:
                logger.warning("No audio data captured")
                return {"success": True, "text": ""}
            
            import numpy as np
            
            # Combine all audio chunks
            audio_data = np.concatenate(self.audio_buffer)
            logger.info(f"Total audio samples: {len(audio_data)}, duration: {len(audio_data)/self.sample_rate:.1f}s")
            
            # Clear buffer
            self.audio_buffer = []
            
            # Convert to float32 normalized to [-1, 1] for Whisper
            audio_float = audio_data.astype(np.float32) / 32768.0
            
            # Resample to 16kHz if needed (Whisper expects 16kHz)
            if self.sample_rate != 16000:
                try:
                    from scipy import signal
                    num_samples = int(len(audio_float) * 16000 / self.sample_rate)
                    audio_float = signal.resample(audio_float, num_samples)
                    logger.info(f"Resampled from {self.sample_rate}Hz to 16000Hz")
                except ImportError:
                    logger.warning("scipy not available, using basic resampling")
                    # Basic resampling fallback
                    ratio = 16000 / self.sample_rate
                    indices = np.arange(0, len(audio_float), 1/ratio).astype(int)
                    indices = indices[indices < len(audio_float)]
                    audio_float = audio_float[indices]
            
            # Transcribe with Whisper
            logger.info("Transcribing with Whisper...")
            try:
                segments, info = self.whisper_model.transcribe(
                    audio_float,
                    language="en",
                    beam_size=5,
                    vad_filter=True,  # Filter out silence
                )
                
                # Combine all segments
                text = " ".join([seg.text.strip() for seg in segments])
                logger.info(f"Whisper transcription: '{text}'")
                
                # Queue the result
                if not hasattr(self, 'transcription_queue'):
                    self.transcription_queue = deque(maxlen=100)
                
                if text:
                    self.transcription_queue.append({
                        "type": "final",
                        "text": text,
                        "timestamp": time.time()
                    })
                
                return {"success": True, "text": text}
                
            except Exception as whisper_error:
                logger.error(f"Whisper transcription failed: {whisper_error}", exc_info=True)
                return {"success": False, "error": f"Transcription failed: {whisper_error}"}
            
        except Exception as e:
            logger.error(f"Error stopping STT: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_transcriptions(self):
        """Get pending transcriptions and clear the queue (polling endpoint)"""
        try:
            # Ensure transcription_queue exists (for static context)
            if not hasattr(self, 'transcription_queue'):
                self.transcription_queue = deque(maxlen=100)
            
            # Get all pending transcriptions
            results = list(self.transcription_queue)
            self.transcription_queue.clear()
            
            if results:
                logger.info(f"Returning {len(results)} transcriptions to frontend")
            
            return {"success": True, "results": results}
        except Exception as e:
            logger.error(f"Error getting transcriptions: {e}", exc_info=True)
            return {"success": False, "results": [], "error": str(e)}


    async def get_setting(self, key: str, default=None):

        """Get a setting value"""
        logger.info(f"Getting setting: {key}")
        return self.settings.get(key, default)

    async def set_setting(self, key: str, value):
        """Set a setting value"""
        logger.info(f"Setting {key} to {value}")
        self.settings[key] = value
        return True

    async def get_microphone_status(self):
        """Check if microphone is available"""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            default_input = sd.query_devices(kind='input')
            
            return {
                "available": True,
                "default_device": default_input['name'] if default_input else None,
                "is_recording": self.is_recording
            }
        except Exception as e:
            logger.error(f"Error checking microphone: {e}")
            return {"available": False, "error": str(e)}

    async def copy_to_clipboard(self, text: str):
        """Copy text to system clipboard using xclip/xsel"""
        logger.info(f"Copying text to clipboard: {text[:50]}..." if len(text) > 50 else f"Copying text to clipboard: {text}")
        try:
            # Try xclip first (most common on Linux)
            try:
                process = subprocess.Popen(
                    ["xclip", "-selection", "clipboard"],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                process.communicate(input=text.encode('utf-8'), timeout=5)
                if process.returncode == 0:
                    logger.info("Successfully copied to clipboard using xclip")
                    return {"success": True}
            except FileNotFoundError:
                pass  # xclip not installed
            except Exception as e:
                logger.warning(f"xclip failed: {e}")
            
            # Try xsel as fallback
            try:
                process = subprocess.Popen(
                    ["xsel", "--clipboard", "--input"],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                process.communicate(input=text.encode('utf-8'), timeout=5)
                if process.returncode == 0:
                    logger.info("Successfully copied to clipboard using xsel")
                    return {"success": True}
            except FileNotFoundError:
                pass  # xsel not installed
            except Exception as e:
                logger.warning(f"xsel failed: {e}")
            
            # Try wl-copy for Wayland
            try:
                process = subprocess.Popen(
                    ["wl-copy"],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                process.communicate(input=text.encode('utf-8'), timeout=5)
                if process.returncode == 0:
                    logger.info("Successfully copied to clipboard using wl-copy")
                    return {"success": True}
            except FileNotFoundError:
                pass  # wl-copy not installed
            except Exception as e:
                logger.warning(f"wl-copy failed: {e}")
            
            logger.error("No clipboard tool available (tried xclip, xsel, wl-copy)")
            return {"success": False, "error": "No clipboard tool available"}
            
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # Asyncio-compatible long-running code, executed in a task when the plugin is loaded
    async def _migration(self):
        logger.info("STT Keyboard plugin migration check")
        # Perform any necessary migrations here
        pass