# STT Keyboard - Speech-to-Text Plugin for Steam Deck

A Decky Loader plugin that adds speech-to-text functionality to your Steam Deck, allowing you to use voice input instead of typing with trackpads.

## Features

- 🎤 **Speech-to-Text Integration**: Convert your speech to text using the built-in microphone or external microphone
- 📋 **Clipboard Integration**: Click to add to your clipboard, then paste anywhere!
- 🎮 **Navigateable with Controllers**: Self explanitory, but as a tip you may want to use the Paste command as a rear button action.
- ⚙️ **Accessible via QAM**: Anytime your quick access menu is available, so is STT!

## Why This Plugin?

Typing on the Steam Deck with trackpads is slow and frustrating. The Steam Deck has a built-in microphone that's rarely utilized. This plugin bridges that gap, allowing you to dictate text much faster than typing - especially useful for:

- Chat messages in games
- Search queries
- Web browsing
- Taking notes
- Any text input scenario

## Installation

In Desktop Mode download the zip file, it will end up in your downloads folder, return to Gamemode and then DeckyLoader in the QAM. Click the gear icon to get to settings. Then go to Developer and enable it so you can install the custom plugin from the downloads folder.

First time usage requires that you install the voice recognition model which is 1.8GB, this may take up to 10 minutes to download, or longer depending on your internet speeds. It is important you stay on the STT plugin screen, don't navigate away from it or close your QAM until the download is complete. Doing either will unload the plugin which will stop the download. 

## Usage

### Basic Usage

1. Open the Decky menu (press the `...` button)
2. Find "STT Keyboard" in the plugin list
3. Click the microphone icon to start or stop recording.
4. Click into the preview text to edit, which supports starting a new recording to type into the cursor position, or replacing text you have highlited with your cursor.
5. Click the clipboard icon to save the text for pasting as you wish.
6. Leaving the plugin screen will reset the text field.

## Technical Details

### Architecture

- **Frontend**: React + TypeScript (Decky Frontend Library)
- **Backend**: Python (runs in Decky Loader's Python environment)
- **Build System**: Rollup (frontend), bundled Python dependencies
- **Speech Recognition**: VOSK (offline speech-to-text engine)
- **Audio Capture**: sounddevice + numpy (48kHz → 16kHz resampling)

### File Structure

```
decky-stt-keyboard/
├── src/
│   ├── services/
│   │   └── SpeechToTextService.ts  # Frontend STT service (polling, callbacks)
│   └── index.tsx                    # Plugin entry point & main UI
├── backend/
│   ├── src/
│   │   └── main.py                  # Python backend (VOSK integration, audio)
│   ├── lib/                         # Bundled Python dependencies (vosk, numpy, etc.)
│   └── requirements.txt
├── defaults/
│   └── settings.json                # Default plugin settings
├── package.json
├── plugin.json
├── tsconfig.json
├── rollup.config.js
└── README.md
```

### Key Dependencies

| Dependency | Purpose |
|------------|---------|
| `vosk` | Offline speech recognition engine |
| `numpy` | Audio processing & resampling |
| `sounddevice` | Microphone input capture |
| `decky-frontend-lib` | Decky Loader UI components |

**Note on Bundled Dependencies:**
The `backend/lib` directory contains standard pre-compiled Python wheels (numpy, vosk, cffi, etc.) extracted from PyPI for Linux x86_64 (Python 3.11). These are bundled to ensure the plugin works out-of-the-box on SteamOS without requiring complex compilation or system modifications.

### Testing

1. Install the plugin
2. Test in various scenarios:
   - Game overlay keyboard
   - Web browser input fields
   - Chat applications
3. Model is Enlglish only, sorry to other language speakers.
 
 ### Debugging

- Check Decky's dev console for logs
- Check /home/deck/homebrew/logs/STT Keyboard
- Delete vosk-model-en-us-0.22 folder and retry download,the Model is downloaded to /home/deck/.local/share/decky-stt-keyboard/models

## Troubleshooting

### Microphone Not Working

1. Check system microphone settings
2. Restart Steam

### Recognition Not Accurate

1. Speak clearly and at a moderate pace
2. Keep SteamDeck within 12" of your face or use an external mic.
3. Reduce background noise

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly on Steam Deck
5. Submit a pull request

## License

GPL-3.0 License - see LICENSE file for details

## Credits

- Built with [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader)
- Uses VOSK offline speech recognition
- Inspired by the accessibility needs of the Steam Deck community

## Support

- [Report Issues](https://github.com/sebastianuxd/decky-stt-keyboard/issues)
- [Discussions](https://github.com/sebastianuxd/decky-stt-keyboard/discussions)
- [Decky Loader Discord](https://deckbrew.xyz/discord)

## Acknowledgments

Thanks to the Steam Deck Homebrew community and all contributors!
