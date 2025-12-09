import logging
import os
import sys
import subprocess
import asyncio
import json
import threading
import time
import zipfile
import urllib.request
import ssl
from collections import deque
from pathlib import Path

# The decky plugin module is located at decky-loader/plugin
import decky
try:
    import decky_plugin
except ImportError:
    decky_plugin = None

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
DATA_DIR = Path(os.environ.get("HOME", "/home/deck")) / ".local/share/decky-stt-keyboard"
BUNDLED_LIB_DIR = PLUGIN_DIR / "lib"

# Add bundled lib to Python path EARLY
if BUNDLED_LIB_DIR.exists() and str(BUNDLED_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(BUNDLED_LIB_DIR))
    logger.info(f"Added bundled lib to sys.path: {BUNDLED_LIB_DIR}")

MODEL_DIR = DATA_DIR / "models"
# Large model for best accuracy (~1.8GB download)
MODEL_NAME = "vosk-model-en-us-0.22"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_PATH = MODEL_DIR / MODEL_NAME

class Plugin:
    """
    STT Keyboard Backend Plugin (Vosk Edition)
    """

    def __init__(self):
        self.settings = {}
        self.output_file = Path("/tmp/stt_output.txt")
        self.model = None
        self.recognizer = None
        self.audio_stream = None
        self.is_recording = False
        self.loop = None
        self.transcription_queue = deque(maxlen=100)
        self.dump_fp = None  # Debug: dump audio to file handling

    @staticmethod
    def play_sound():
        """Play the start listening sound"""
        sound_paths = [
            "/usr/share/sounds/freedesktop/stereo/bell.oga",
            "/usr/share/sounds/freedesktop/stereo/message.oga",
            "/usr/share/sounds/freedesktop/stereo/service-login.oga",
        ]
        
        for sound_path in sound_paths:
            if os.path.exists(sound_path):
                try:
                    subprocess.run(["paplay", sound_path], stderr=subprocess.PIPE, stdout=subprocess.PIPE, timeout=2)
                    return
                except:
                    continue

    def emit_event(self, event_name: str, data: dict):
        """Emit an event to the frontend"""
        try:
            # Try to emit via decky directly first (synchronous-safe)
            if hasattr(decky, 'emit'):
                try:
                    # decky.emit may be sync or async, handle both
                    result = decky.emit(event_name, data)
                    if asyncio.iscoroutine(result):
                        if self.loop and self.loop.is_running():
                            asyncio.run_coroutine_threadsafe(result, self.loop)
                    return
                except Exception as e:
                    logger.debug(f"decky.emit failed, trying fallback: {e}")
            
            # Fallback to async emit via loop
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self._emit_async(event_name, data), self.loop)
        except Exception as e:
            logger.error(f"Failed to emit event {event_name}: {e}")

    async def _emit_async(self, event_name: str, data: dict):
        try:
            if hasattr(self, "emit"):
                await self.emit(event_name, data)
            elif decky_plugin and hasattr(decky_plugin, "emit"):
                result = decky_plugin.emit(event_name, data)
                if asyncio.iscoroutine(result):
                    await result
            elif hasattr(decky, "emit"):
                result = decky.emit(event_name, data)
                if asyncio.iscoroutine(result):
                    await result
        except Exception as e:
            logger.error(f"Error in _emit_async: {e}")

    async def _main(self):
        try:
            self.loop = asyncio.get_running_loop()
            
            # Initialize attributes if running as class
            if isinstance(self, type):
                if not hasattr(self, "settings"): self.settings = {}
                if not hasattr(self, "model"): self.model = None
                if not hasattr(self, "recognizer"): self.recognizer = None
                if not hasattr(self, "audio_stream"): self.audio_stream = None
                if not hasattr(self, "is_recording"): self.is_recording = False
                if not hasattr(self, "transcription_queue"): self.transcription_queue = deque(maxlen=100)

            DATA_DIR.mkdir(parents=True, exist_ok=True)
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            
            if not await Plugin._ensure_dependencies():
                logger.error("Failed to ensure dependencies")

            logger.info("STT Keyboard: Plugin loaded successfully")
        except Exception as e:
            logger.error(f"STT Keyboard initialization error: {e}", exc_info=True)

    async def _unload(self):
        if isinstance(self, type):
            await Plugin.stop_stt(self)
        else:
            await self.stop_stt()
        logger.info("STT Keyboard plugin unloaded")

    @staticmethod
    async def _ensure_dependencies():
        try:
            import sounddevice
            import numpy
            import vosk
            logger.info("Dependencies imported: sounddevice, numpy, vosk")
            return True
        except ImportError as e:
            logger.error(f"Failed to import dependencies: {e}")
            return False

    async def get_model_status(self):
        downloaded = MODEL_PATH.exists()
        return {
            "downloaded": downloaded,
            "path": str(MODEL_PATH) if downloaded else "",
            "name": MODEL_NAME
        }

    async def download_model(self):
        logger.info(f"Downloading model from {MODEL_URL}")
        try:
            if not MODEL_DIR.exists():
                MODEL_DIR.mkdir(parents=True, exist_ok=True)

            zip_path = MODEL_DIR / f"{MODEL_NAME}.zip"
            
            # Download with progress
            plugin_self = self
            def progress_hook(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                if count % 100 == 0:
                    if isinstance(plugin_self, type):
                        Plugin.emit_event(plugin_self, "download_progress", {"percent": percent})
                    else:
                        plugin_self.emit_event("download_progress", {"percent": percent})
            
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-agent', 'Mozilla/5.0')]
            urllib.request.install_opener(opener)
            
            urllib.request.urlretrieve(MODEL_URL, zip_path, reporthook=progress_hook)
            logger.info("Download complete. Extracting...")
            if isinstance(plugin_self, type):
                Plugin.emit_event(plugin_self, "download_progress", {"percent": 100, "status": "Extracting..."})
            else:
                plugin_self.emit_event("download_progress", {"percent": 100, "status": "Extracting..."})
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(MODEL_DIR)
            
            if zip_path.exists():
                os.remove(zip_path)
                
            logger.info("Model extracted successfully")
            
            # Auto-load model
            if isinstance(plugin_self, type):
                await Plugin.load_model(plugin_self)
            else:
                await plugin_self.load_model()
            
            return {"success": True}
        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def load_model(self):
        try:
            if self.model is not None:
                return {"success": True}
                
            if not MODEL_PATH.exists():
                return {"success": False, "error": "Model not downloaded"}

            import vosk
            vosk.SetLogLevel(-1) # Silence generic logs
            logger.info(f"Loading Vosk model from {MODEL_PATH}")
            self.model = vosk.Model(str(MODEL_PATH))
            logger.info("Vosk model loaded")
            return {"success": True}
        except Exception as e:
            logger.error(f"Load model failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _audio_callback(self, indata, frames, time_info, status):
        try:
            if status:
                logger.warning(f"Audio status: {status}")
            
            import numpy as np
            
            # Convert to numpy array (float for processing)
            audio_array = np.frombuffer(indata, dtype=np.int16).copy().astype(np.float32)
            
            # Debug: Log periodically to confirm callback is working
            if not hasattr(self, '_callback_count'):
                self._callback_count = 0
            self._callback_count += 1
            if self._callback_count % 50 == 1:  # Log every 50 callbacks
                logger.info(f"Audio callback #{self._callback_count}: buffer size={len(audio_array)}, rms={np.sqrt(np.mean(audio_array ** 2)):.1f}")
            
            # ===== MINIMAL PROCESSING =====
            # NOTE: Noise reduction disabled - VOSK handles noise well on its own
            # Complex filtering was hurting accuracy more than helping
            
            # Just apply clip protection to prevent distortion
            audio_array = np.clip(audio_array, -32767, 32767)
            
            # Convert back to int16 for VOSK
            audio_int16 = audio_array.astype(np.int16)

            # Pass to recognizer
            if self.recognizer and self.recognizer.AcceptWaveform(audio_int16.tobytes()):
                res = json.loads(self.recognizer.Result())
                text = res.get("text", "")
                if text:
                    logger.info(f"Final result: {text}")
                    # Store in queue for polling
                    self.transcription_queue.append({"result": text, "final": True})
                    if isinstance(self, type):
                        Plugin.emit_event(self, "stt_result", {"result": text, "final": True})
                    else:
                        self.emit_event("stt_result", {"result": text, "final": True})
            else:
                if self.recognizer:
                    partial = json.loads(self.recognizer.PartialResult())
                    text = partial.get("partial", "")
                    if text:
                        logger.info(f"Partial result: {text}")
                        # Store in queue for polling (only newest partial to avoid spam)
                        # Remove old partials first
                        while self.transcription_queue and not self.transcription_queue[-1].get("final"):
                            self.transcription_queue.pop()
                        self.transcription_queue.append({"result": text, "final": False})
                        if isinstance(self, type):
                            Plugin.emit_event(self, "stt_result", {"result": text, "final": False})
                        else:
                            self.emit_event("stt_result", {"result": text, "final": False})

        except Exception as e:
            logger.error(f"Callback error: {e}", exc_info=True)

    async def start_stt(self, language: str = "en-US"):
        if self.is_recording: return {"success": False, "error": "Already recording"}
        
        # Load model if needed
        if self.model is None:
            if isinstance(self, type):
                await Plugin.load_model(self)
            else:
                await self.load_model()
            if self.model is None:
                return {"success": False, "error": "Model failed to load"}

        try:
            import sounddevice as sd
            import vosk
            import numpy as np
            
            self.recognizer = vosk.KaldiRecognizer(self.model, 16000)
            self.play_sound()
            
            # Get device's default sample rate
            device_info = sd.query_devices(kind='input')
            device_samplerate = int(device_info['default_samplerate'])
            logger.info(f"Using device sample rate: {device_samplerate}")
            
            # Calculate resampling parameters
            target_samplerate = 16000
            resample_ratio = device_samplerate / target_samplerate
            
            # Define callback wrapper with linear interpolation resampling
            plugin_self = self
            def callback_wrapper(indata, frames, time_info, status):
                try:
                    # Resample from device rate to 16kHz using linear interpolation
                    audio_data = np.frombuffer(indata, dtype=np.int16).astype(np.float32)
                    
                    if resample_ratio != 1.0:
                        # Linear interpolation resampling (much better quality than decimation)
                        old_length = len(audio_data)
                        new_length = int(old_length / resample_ratio)
                        old_indices = np.arange(old_length)
                        new_indices = np.linspace(0, old_length - 1, new_length)
                        resampled = np.interp(new_indices, old_indices, audio_data).astype(np.int16)
                    else:
                        resampled = audio_data.astype(np.int16)
                    
                    # Call the audio callback with resampled data
                    if isinstance(plugin_self, type):
                        Plugin._audio_callback(plugin_self, resampled.tobytes(), len(resampled), time_info, status)
                    else:
                        plugin_self._audio_callback(resampled.tobytes(), len(resampled), time_info, status)
                except Exception as e:
                    logger.error(f"Callback wrapper error: {e}")

            logger.info("Starting stream...")
            # Use smaller blocksize for faster response (2000 samples @ 16kHz = 125ms)
            blocksize = int(2000 * resample_ratio)
            self.audio_stream = sd.RawInputStream(
                samplerate=device_samplerate, 
                blocksize=blocksize, 
                dtype='int16', 
                channels=1, 
                callback=callback_wrapper
            )
            self.audio_stream.start()
            self.is_recording = True
            return {"success": True}
        except Exception as e:
            logger.error(f"Start failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def stop_stt(self):
        if not self.is_recording: return {"success": True}
        
        try:
            if self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream.close()
                self.audio_stream = None
            
            self.is_recording = False
            
            # Get final result
            if self.recognizer:
                res = json.loads(self.recognizer.FinalResult())
                text = res.get("text", "")
                if text:
                    if isinstance(self, type):
                        Plugin.emit_event(self, "stt_result", {"result": text, "final": True})
                    else:
                        self.emit_event("stt_result", {"result": text, "final": True})
            
            return {"success": True}
        except Exception as e:
            logger.error(f"Stop failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_microphone_status(self):
        try:
            import sounddevice as sd
            d = sd.query_devices(kind='input')
            return {"available": True, "device": d['name'] if d else "Default", "is_recording": self.is_recording}
        except:
            return {"available": False}

    async def get_pending_results(self):
        """Get pending transcription results for polling - clears queue after read"""
        results = list(self.transcription_queue)
        self.transcription_queue.clear()
        return {"results": results, "is_recording": self.is_recording}

    async def copy_to_clipboard(self, text: str):
        # Implementation from previous fixes (xclip/xsel/wl-copy/qdbus)
        try:
            # Try qdbus (KDE/SteamDeck standard)
            try:
                p = subprocess.run(["qdbus", "org.kde.klipper", "/klipper", "setClipboardContents", text], 
                                stderr=subprocess.PIPE, timeout=2)
                if p.returncode == 0: return {"success": True}
            except: pass

            # Try wl-copy
            try:
                p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                p.communicate(input=text.encode('utf-8'), timeout=2)
                if p.returncode == 0: return {"success": True}
            except: pass
            
            # Try xclip
            try:
                p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                p.communicate(input=text.encode('utf-8'), timeout=2)
                if p.returncode == 0: return {"success": True}
            except: pass

            return {"success": False, "error": "No clipboard tool worked"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_transcriptions(self):
        return {"success": True, "results": []} # Vosk pushes events, no polling needed really, but kept for API compat