import logging
import os

# The decky plugin module is located at decky-loader/plugin
# For the hosted code: `import decky` works, but the actual source is in decky-loader/plugin/decky.py
import decky

logging.basicConfig(
    level=logging.INFO,
    format="[STT Keyboard] %(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger()


class Plugin:
    """
    STT Keyboard Backend Plugin
    
    This plugin primarily runs on the frontend using Web Speech API,
    so the backend is minimal and mainly used for settings persistence
    and potential future features.
    """

    async def _main(self):
        logger.info("=" * 60)
        logger.info("STT KEYBOARD PLUGIN: _main() CALLED - STARTING INITIALIZATION")
        logger.info("=" * 60)
        try:
            self.settings = {}
            logger.info("STT Keyboard: Settings initialized successfully")
            logger.info("STT Keyboard: Plugin loaded successfully")
        except Exception as e:
            logger.error(f"STT Keyboard: Error during initialization: {e}", exc_info=True)
            raise

    async def _unload(self):
        logger.info("STT Keyboard plugin unloaded")
        pass

    async def get_setting(self, key: str, default=None):
        """
        Get a setting value
        """
        logger.info(f"Getting setting: {key}")
        return self.settings.get(key, default)

    async def set_setting(self, key: str, value):
        """
        Set a setting value
        """
        logger.info(f"Setting {key} to {value}")
        self.settings[key] = value
        return True

    async def get_microphone_status(self):
        """
        Check if microphone is available (future implementation)
        """
        # This would require system-level checks
        # For now, return a placeholder
        return {"available": True, "message": "Microphone status check not implemented"}

    async def test_speech_recognition(self):
        """
        Test speech recognition capability (future implementation)
        """
        return {"supported": True, "message": "Speech recognition testing from backend not implemented"}

    # Asyncio-compatible long-running code, executed in a task when the plugin is loaded
    async def _migration(self):
        logger.info("STT Keyboard plugin migration check")
        # Perform any necessary migrations here
        pass