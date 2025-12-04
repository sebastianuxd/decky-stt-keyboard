# Contributing to STT Keyboard

Thank you for your interest in contributing to the STT Keyboard plugin for Steam Deck! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Node.js 16+ and pnpm
- Steam Deck (for testing) or SteamOS environment
- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) installed
- Basic knowledge of TypeScript, React, and Decky plugin development

### Getting Started

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/decky-stt-keyboard.git
   cd decky-stt-keyboard
   ```

2. **Install Dependencies**
   ```bash
   pnpm install
   ```

3. **Development Build**
   ```bash
   # Watch mode for auto-rebuild
   pnpm run watch
   ```

4. **Deploy to Steam Deck**
   ```bash
   # Set your Steam Deck's IP
   export DECK_IP=192.168.1.XXX
   
   # Deploy
   pnpm run deploy
   ```

## Project Structure

```
decky-stt-keyboard/
├── src/
│   ├── components/        # React components
│   ├── services/          # Business logic services
│   └── index.tsx          # Plugin entry point
├── defaults/              # Default configuration
├── main.py                # Python backend
├── plugin.json            # Plugin metadata
└── package.json           # Node dependencies
```

## Code Style

- Use TypeScript for all frontend code
- Follow existing code formatting
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions small and focused

## Testing

Before submitting a PR, please test:

1. **Basic Functionality**
   - Speech recognition starts/stops correctly
   - Text is inserted into active input fields
   - Settings are saved and persisted

2. **Keyboard Shortcuts**
   - Ctrl+Shift+S works on desktop
   - Steam+Y works on Steam Deck
   - No conflicts with existing shortcuts

3. **Edge Cases**
   - No microphone available
   - No internet connection
   - Multiple rapid activations
   - Different languages

4. **UI/UX**
   - Overlay appears and closes properly
   - Buttons are responsive
   - Error messages are clear

## Pull Request Process

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Write clear, concise commits
   - Follow the existing code style
   - Add comments where needed

3. **Test Thoroughly**
   - Test on Steam Deck if possible
   - Verify no regressions
   - Check console for errors

4. **Submit PR**
   - Provide a clear description
   - Reference any related issues
   - Include screenshots/videos if applicable

## Reporting Issues

When reporting issues, please include:

- Plugin version
- SteamOS version
- Steps to reproduce
- Expected vs actual behavior
- Console logs (if applicable)
- Screenshots/videos (if applicable)

## Feature Requests

We welcome feature requests! Please:

- Check if it's already requested
- Explain the use case
- Describe the desired behavior
- Consider implementation complexity

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Help others learn and grow

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0 License.

## Questions?

Feel free to:
- Open a discussion on GitHub
- Ask in the Decky Loader Discord
- Tag maintainers in issues/PRs

Thank you for contributing! 🎉