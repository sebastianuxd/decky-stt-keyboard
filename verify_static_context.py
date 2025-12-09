
import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock

# Mock dependencies
sys.modules['decky'] = MagicMock()
sys.modules['decky_plugin'] = MagicMock()
sys.modules['ssl'] = MagicMock()
sys.modules['vosk'] = MagicMock()
sys.modules['sounddevice'] = MagicMock()
sys.modules['numpy'] = MagicMock()

# Import the Plugin class (we need to be able to import it)
# We need to add backend/src to sys.path
import os
sys.path.append(os.path.abspath("backend/src"))

try:
    from main import Plugin
except ImportError:
    print("Could not import Plugin from backend/src/main.py")
    sys.exit(1)

# Mock some Plugin methods/attributes that rely on external things
Plugin.get_model_status = AsyncMock(return_value={"downloaded": True, "path": "/tmp/model", "name": "vosk"})
Plugin.emit_event = MagicMock()

async def mock_load_model(self):
    print(f"load_model called (self type: {type(self)})")
    # Simulate the check inside load_model
    # The real load_model calls self.get_model_status() which fails if self is class and get_model_status is instance method called without instance
    # But wait, get_model_status is async.
    return {"success": True}

# We want to test the REAL start_stt and load_model logic regarding SELF usage.
# So we shouldn't mock them away if we want to test the fix.
# However, for reproduction, we want to see it fail.

async def reproduction():
    print("--- Starting Reproduction ---")
    p = Plugin # Static context
    
    # Initialize attributes as done in _main
    if not hasattr(p, "settings"): p.settings = {}
    if not hasattr(p, "vosk_model"): p.vosk_model = None
    if not hasattr(p, "recognizer"): p.recognizer = None
    if not hasattr(p, "audio_stream"): p.audio_stream = None
    if not hasattr(p, "is_recording"): p.is_recording = False
    
    # Mock sounddevice.query_devices to return 48000
    p.audio_stream = None # Ensure it is reset
    
    print("Calling start_stt on Plugin class...")
    try:
        # If I call Plugin.start_stt(Plugin), `self` is Plugin class.
        await Plugin.start_stt(Plugin) 
        print("Success: start_stt executed without error")
        # Verify calls
        # We need to verify that KaldiRecognizer was called with 48000 (from our mock)
        # But we mocked sys.modules['vosk'] at top level, how to check?
        import vosk
        # vosk.KaldiRecognizer.assert_called_with(p.vosk_model, 48000)
        # We can't easily assert here because we re-imported vosk inside start_stt which uses the system modules mock.
        
    except TypeError as e:
        print(f"Caught expected TypeError: {e}")
    except Exception as e:
        print(f"Caught unexpected exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    from unittest.mock import AsyncMock
    # Patching dependencies that would actually run
    Plugin.get_model_status = AsyncMock(return_value={"downloaded": True, "path": "test", "name": "test"})
    
    # SETUP MOCKS FOR TESTS
    import sounddevice
    sounddevice.query_devices = MagicMock(return_value={'default_samplerate': 48000, 'name': 'Mock Device'})
    sounddevice.RawInputStream = MagicMock()
    
    import vosk
    vosk.KaldiRecognizer = MagicMock()
    
    # Ensure sys.modules['decky'].emit is a mock we can check
    global decky
    import decky
    decky.emit = MagicMock()

    
    asyncio.run(reproduction())
