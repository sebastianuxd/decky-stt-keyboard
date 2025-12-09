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
# Using a better quality but still lightweight model
MODEL_NAME = "vosk-model-en-us-0.22-lgraph"
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
            
            if not await self._ensure_dependencies():
                logger.error("Failed to ensure dependencies")

            logger.info("STT Keyboard: Plugin loaded successfully")
        except Exception as e:
            logger.error(f"STT Keyboard initialization error: {e}", exc_info=True)

    async def _unload(self):
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
            await self.load_model()
            
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
            
            # ===== NOISE REDUCTION PIPELINE =====
            
            # 1. NOISE GATE - Silence audio below threshold (removes background noise)
            noise_threshold = 150  # Adjust based on mic sensitivity (int16 range: 0-32767)
            rms = np.sqrt(np.mean(audio_array ** 2))
            if rms < noise_threshold:
                # Very quiet - likely just noise, zero it out
                audio_array = np.zeros_like(audio_array)
            
            # 2. HIGH-PASS FILTER - Remove low frequency rumble (< ~100Hz)
            # Simple first-order high-pass filter using difference
            if len(audio_array) > 1:
                # Alpha controls cutoff: higher = more bass removed
                # For 16kHz sample rate, alpha ~0.97 gives ~80Hz cutoff
                alpha = 0.97
                filtered = np.zeros_like(audio_array)
                filtered[0] = audio_array[0]
                for i in range(1, len(audio_array)):
                    filtered[i] = alpha * (filtered[i-1] + audio_array[i] - audio_array[i-1])
                audio_array = filtered
            
            # 3. SOFT NOISE GATE - Reduce (don't eliminate) quiet sections
            # This preserves speech tails while reducing constant background
            soft_threshold = 300
            if rms > noise_threshold and rms < soft_threshold:
                # Reduce volume of borderline audio
                reduction = rms / soft_threshold  # 0.5 to 1.0
                audio_array = audio_array * reduction
            
            # 4. GAIN NORMALIZATION - Boost quiet speech
            max_val = np.max(np.abs(audio_array))
            if max_val > 0:
                # Target roughly 60% of max range (32767)
                target = 20000 
                if max_val < target:
                    gain = min(target / max_val, 10.0)  # Max 10x boost
                    if gain > 1.2:
                        audio_array = audio_array * gain
            
            # 5. CLIP PROTECTION - Prevent distortion
            audio_array = np.clip(audio_array, -32767, 32767)
            
            # Convert back to int16 for VOSK
            audio_int16 = audio_array.astype(np.int16)

            # Pass to recognizer
            if self.recognizer and self.recognizer.AcceptWaveform(audio_int16.tobytes()):
                res = json.loads(self.recognizer.Result())
                text = res.get("text", "")
                if text:
                    self.emit_event("stt_result", {"result": text, "final": True})
            else:
                if self.recognizer:
                    partial = json.loads(self.recognizer.PartialResult())
                    text = partial.get("partial", "")
                    if text:
                         self.emit_event("stt_result", {"result": text, "final": False})

        except Exception as e:
            logger.error(f"Callback error: {e}")

    async def start_stt(self):
        if self.is_recording: return {"success": False, "error": "Already recording"}
        
        # Load model if needed
        if self.model is None:
            await self.load_model()
            if self.model is None:
                return {"success": False, "error": "Model failed to load"}

        try:
            import sounddevice as sd
            import vosk
            
            self.recognizer = vosk.KaldiRecognizer(self.model, 16000)
            self.play_sound()
            
            # Define callback wrapper
            plugin_self = self
            def callback_wrapper(indata, frames, time_info, status):
                if isinstance(plugin_self, type):
                    Plugin._audio_callback(plugin_self, indata, frames, time_info, status)
                else:
                    plugin_self._audio_callback(indata, frames, time_info, status)

            logger.info("Starting stream...")
            self.audio_stream = sd.RawInputStream(
                samplerate=16000, 
                blocksize=4000, 
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