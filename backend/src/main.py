import logging
import os
import sys
import subprocess
import asyncio
import json
import threading
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
MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_PATH = MODEL_DIR / MODEL_NAME
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"


class Plugin:
    """
    STT Keyboard Backend Plugin
    
    Handles offline speech recognition using Vosk and sounddevice
    for microphone access without browser permission issues.
    """

    def __init__(self):
        self.settings = {}
        self.vosk_model = None
        self.recognizer = None
        self.audio_stream = None
        self.is_recording = False
        self.recording_thread = None
        self.loop = None

    def emit_event(self, event_name: str, data: dict):
        """Emit an event to the frontend"""
        try:
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self._emit_async(event_name, data), self.loop)
            else:
                logger.warning(f"Event loop not ready, cannot emit {event_name}")
        except Exception as e:
            logger.error(f"Failed to emit event {event_name}: {e}")

    async def _emit_async(self, event_name: str, data: dict):
        try:
            # Try to use self.emit (Decky Plugin API)
            if hasattr(self, "emit"):
                await self.emit(event_name, data)
            elif decky_plugin and hasattr(decky_plugin, "emit_event"):
                decky_plugin.emit_event(event_name, data)
            elif hasattr(decky, "emit_event"):
                # Fallback to decky module
                decky.emit_event(event_name, data)
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
            if not hasattr(self, "vosk_model"): self.vosk_model = None
            if not hasattr(self, "recognizer"): self.recognizer = None
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
                import vosk
                import sounddevice
                import numpy
                logger.info("All dependencies successfully imported")
                return True
            except ImportError as e:
                logger.error(f"Failed to import dependencies despite adding lib to path: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error ensuring dependencies: {e}", exc_info=True)
            return False

    async def get_model_status(self):
        """Check if the Vosk model is downloaded"""
        model_exists = MODEL_PATH.exists() and (MODEL_PATH / "am").exists()
        return {
            "downloaded": model_exists,
            "path": str(MODEL_PATH),
            "name": MODEL_NAME
        }

    async def download_model(self):
        """Download the Vosk speech recognition model"""
        try:
            import urllib.request
            import zipfile
            
            # Ensure model directory exists
            if not MODEL_DIR.exists():
                try:
                    MODEL_DIR.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    return {"success": False, "error": f"Failed to create model directory: {e}"}

            logger.info(f"Downloading model from {MODEL_URL}")
            
            zip_path = MODEL_DIR / f"{MODEL_NAME}.zip"
            
            # Download with progress - capture self in closure explicitly
            plugin_instance = self
            def download_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                percent = min(100, (downloaded / total_size) * 100)
                plugin_instance.emit_event("stt_download_progress", {"percent": percent})
            
            urllib.request.urlretrieve(MODEL_URL, zip_path, download_progress)
            
            logger.info("Extracting model...")
            self.emit_event("stt_download_progress", {"percent": 100, "status": "extracting"})
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(MODEL_DIR)
            
            # Clean up zip file
            zip_path.unlink()
            
            logger.info("Model downloaded and extracted successfully")
            self.emit_event("stt_download_complete", {"success": True})
            return {"success": True, "path": str(MODEL_PATH)}
            
        except Exception as e:
            logger.error(f"Error downloading model: {e}", exc_info=True)
            self.emit_event("stt_download_complete", {"success": False, "error": str(e)})
            return {"success": False, "error": str(e)}

    async def load_model(self):
        """Load the Vosk model into memory"""
        try:
            if self.vosk_model is not None:
                logger.info("Model already loaded")
                return {"success": True}
            
            # Check if model exists
            status = await self.get_model_status()
            if not status["downloaded"]:
                return {"success": False, "error": "Model not downloaded"}
            
            import vosk
            
            logger.info(f"Loading model from {MODEL_PATH}")
            self.vosk_model = vosk.Model(str(MODEL_PATH))
            
            logger.info("Model loaded successfully")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error loading model: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream - processes audio data"""
        try:
            if status:
                logger.warning(f"Audio callback status: {status}")
            
            if self.recognizer is None:
                return
            
            # Convert audio data to bytes
            audio_data = bytes(indata)
            
            # Process with Vosk
            if self.recognizer.AcceptWaveform(audio_data):
                # Final result
                result = json.loads(self.recognizer.Result())
                if result.get("text"):
                    self.emit_event("stt_final", {"text": result["text"]})
            else:
                # Partial result
                partial = json.loads(self.recognizer.PartialResult())
                if partial.get("partial"):
                    self.emit_event("stt_partial", {"text": partial["partial"]})
                    
        except Exception as e:
            logger.error(f"Error in audio callback: {e}", exc_info=True)

    async def start_stt(self, language: str = "en-US"):
        """Start speech-to-text recording"""
        try:
            if self.is_recording:
                logger.warning("STT already recording")
                return {"success": False, "error": "Already recording"}
            
            # Ensure model is loaded
            if self.vosk_model is None:
                load_result = await self.load_model()
                if not load_result["success"]:
                    return load_result
            
            import vosk
            import sounddevice as sd
            
            # Create recognizer
            self.recognizer = vosk.KaldiRecognizer(self.vosk_model, 16000)
            
            # Start audio stream
            logger.info("Starting audio recording...")
            self.audio_stream = sd.RawInputStream(
                samplerate=16000,
                blocksize=8000,
                dtype='int16',
                channels=1,
                callback=self._audio_callback
            )
            
            self.audio_stream.start()
            self.is_recording = True
            
            self.emit_event("stt_started", {"success": True})
            logger.info("STT recording started")
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error starting STT: {e}", exc_info=True)
            self.emit_event("stt_error", {"error": str(e)})
            return {"success": False, "error": str(e)}

    async def stop_stt(self):
        """Stop speech-to-text recording"""
        logger.info(f"stop_stt called. self type: {type(self)}")
        try:
            # Handle static context where self might be the class but attributes are on the class
            if isinstance(self, type):
                is_recording = getattr(self, "is_recording", False)
            else:
                is_recording = self.is_recording

            if not is_recording:
                logger.info("stop_stt: Not recording, nothing to stop")
                return {"success": True}
            
            logger.info("Stopping STT recording...")
            
            if self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream.close()
                self.audio_stream = None
            
            self.recognizer = None
            self.is_recording = False
            
            self.emit_event("stt_stopped", {"success": True})
            logger.info("STT recording stopped")
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error stopping STT: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

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

    # Asyncio-compatible long-running code, executed in a task when the plugin is loaded
    async def _migration(self):
        logger.info("STT Keyboard plugin migration check")
        # Perform any necessary migrations here
        pass