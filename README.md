# STT Keyboard - Speech-to-Text Plugin for Steam Deck

A Decky Loader plugin that adds speech-to-text functionality to your Steam Deck, allowing you to use voice input instead of typing with trackpads.

## Features

- 🎤 **Speech-to-Text Integration**: Convert your speech to text using the built-in microphone
- ⌨️ **Custom Keyboard Overlay**: Beautiful UI overlay for speech recognition
- 🎮 **Hotkey Support**: Activate with Steam + Y (customizable)
- 🎯 **Chord Command Support**: Quick access through chord commands
- ⚙️ **Configurable Settings**: Auto-submit, language selection, and more
- 🌍 **Multi-language Support**: Choose your preferred language for recognition
- 📋 **Clipboard Integration**: Automatic text insertion or clipboard copy

## Why This Plugin?

Typing on the Steam Deck with trackpads is notoriously slow and frustrating. The Steam Deck has a built-in microphone that's rarely utilized. This plugin bridges that gap, allowing you to dictate text much faster than typing - especially useful for:

- Chat messages in games
- Search queries
- Web browsing
- Taking notes
- Any text input scenario

## Installation

### Prerequisites

- Steam Deck with SteamOS
- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) installed

### Method 1: Via Decky Plugin Store (Recommended)

1. Open Decky Loader on your Steam Deck
2. Navigate to the Plugin Store
3. Search for "STT Keyboard"
4. Click Install

### Method 2: Manual Installation

1. Clone or download this repository
2. Install dependencies and build:
   ```bash
   cd decky-stt-keyboard
   pnpm install
   pnpm run build
   ```
3. Copy the plugin to Decky's plugin directory:
   ```bash
   cp -r dist/* ~/homebrew/plugins/decky-stt-keyboard/
   ```
4. Restart Decky Loader or reload plugins

### Method 3: Development Mode

For development and testing:

```bash
# Install dependencies
pnpm install

# Start watch mode for auto-rebuild
pnpm run watch

# In another terminal, deploy to Steam Deck (requires SSH access)
export DECK_IP=192.168.1.XXX  # Your Steam Deck's IP
pnpm run deploy
```

## Usage

### Basic Usage

1. Open the Decky menu (press the `...` button)
2. Find "STT Keyboard" in the plugin list
3. Toggle "Enable Speech-to-Text"
4. Click "Test Speech-to-Text" or use the hotkey

### Hotkey Activation

- Press **Steam + Y** to activate speech-to-text
- Speak into the microphone
- The text will be automatically inserted into the active input field

### Settings

- **Enable Speech-to-Text**: Toggle the feature on/off
- **Auto-submit**: Automatically submit text after recognition completes
- **Language**: Select your preferred language for recognition

## Browser Compatibility

This plugin uses the Web Speech API, which is supported in Chromium-based browsers (including Steam's built-in browser). The API requires:

- HTTPS connection (or localhost)
- Microphone permissions granted
- Active internet connection (for cloud-based recognition)

## Technical Details

### Architecture

- **Frontend**: React + TypeScript
- **Build System**: Rollup
- **Speech Recognition**: Web Speech API (Chrome's implementation)
- **Integration**: Decky Frontend Library

### File Structure

```
decky-stt-keyboard/
├── src/
│   ├── components/
│   │   └── KeyboardOverlay.tsx    # Main UI overlay
│   ├── services/
│   │   ├── SpeechToTextService.ts # Speech recognition logic
│   │   └── SettingsManager.ts     # Settings persistence
│   └── index.tsx                   # Plugin entry point
├── package.json
├── plugin.json
├── tsconfig.json
├── rollup.config.js
└── README.md
```

### Key Components

#### SpeechToTextService
Handles all speech recognition functionality:
- Initializes Web Speech API
- Manages recognition lifecycle
- Processes results and errors
- Supports multiple languages

#### KeyboardOverlay
Custom UI overlay for speech input:
- Real-time transcript display
- Interim results (live preview)
- Recording controls
- Error handling and display

#### SettingsManager
Persists user preferences:
- Uses localStorage
- Type-safe settings access
- Automatic save on change

## Development

### Building

```bash
# Install dependencies
pnpm install

# Build for production
pnpm run build

# Watch mode for development
pnpm run watch
```

### Testing

1. Build the plugin
2. Deploy to your Steam Deck
3. Test in various scenarios:
   - Game overlay keyboard
   - Web browser input fields
   - Chat applications
   - Different languages

### Debugging

- Check browser console for logs
- Use Decky's developer tools
- Monitor microphone permissions
- Test network connectivity

## Troubleshooting

### Microphone Not Working

1. Check system microphone settings
2. Grant microphone permissions to Steam
3. Test microphone in system settings
4. Restart Steam

### Recognition Not Accurate

1. Speak clearly and at a moderate pace
2. Reduce background noise
3. Check language settings
4. Ensure good internet connection

### Plugin Not Loading

1. Verify Decky Loader is running
2. Check plugin directory structure
3. Review Decky logs for errors
4. Try reinstalling the plugin

### No Text Insertion

1. Ensure an input field is focused
2. Check if auto-submit is enabled
3. Try using clipboard fallback
4. Verify browser compatibility

## Roadmap

- [ ] Offline speech recognition support
- [ ] Custom vocabulary/commands
- [ ] Multiple language quick-switch
- [ ] Punctuation voice commands
- [ ] Integration with Steam's native keyboard
- [ ] Custom hotkey configuration UI
- [ ] Voice command macros
- [ ] Wake word activation

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
- Uses Web Speech API
- Inspired by the Steam Deck community's need for better input methods

## Support

- [Report Issues](https://github.com/yourusername/decky-stt-keyboard/issues)
- [Discussions](https://github.com/yourusername/decky-stt-keyboard/discussions)
- [Decky Loader Discord](https://deckbrew.xyz/discord)

## Acknowledgments

Thanks to the Steam Deck Homebrew community and all contributors!

---

**Note**: This plugin requires an active internet connection for speech recognition as it uses cloud-based processing. Offline support is planned for future releases.