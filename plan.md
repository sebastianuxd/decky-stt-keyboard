# Architecture Plan: Offline STT & Keyboard Integration

## 1. Overview
To resolve microphone permission issues in Game Mode and enable usage without an internet connection, we will migrate the Speech-to-Text (STT) logic from the frontend (Web Speech API) to the backend (Python + Vosk). We will also inject a microphone button directly into the Steam Deck virtual keyboard.

## 2. Backend Architecture (Python)

### Dependency Management
Since the Steam Deck system partition is read-only, we cannot install global pip packages.
- **Strategy**: Vendor dependencies into a `backend/lib` directory.
- **Libraries**:
  - `vosk`: Offline speech recognition engine.
  - `sounddevice`: Audio capture (PortAudio wrapper).
  - `numpy`: Required for audio data processing.
- **Implementation**: On plugin load, check if dependencies exist in `backend/lib`. If not, run `pip install -t backend/lib -r requirements.txt`. Add `backend/lib` to `sys.path`.

### Model Management
- **Model**: `vosk-model-small-en-us-0.15` (Lightweight, ~40MB).
- **Storage**: `backend/models/`.
- **Logic**:
  - Check if model exists on startup.
  - If missing, expose a `download_model()` method to the frontend.
  - Provide status updates (download progress) to frontend.

### Audio Processing Loop
- **Input**: `sounddevice.RawInputStream` (captures raw audio data).
- **Processing**: Feed data chunks to `vosk.KaldiRecognizer`.
- **Output**:
  - `stt_partial`: Real-time text updates (for "listening..." feedback).
  - `stt_final`: Completed sentence/phrase.
  - `stt_error`: Microphone or recognition errors.
- **Communication**: Use `decky.plugin.send_to_frontend` to emit events.

## 3. Frontend Architecture (React/TypeScript)

### SpeechToTextService Refactor
- Remove `window.SpeechRecognition` logic.
- Implement `ServerAPI` calls:
  - `start()` -> calls backend `start_stt`.
  - `stop()` -> calls backend `stop_stt`.
- Listen for backend events (`stt_partial`, `stt_final`) to update the UI.

### KeyboardInjector Service
- **Goal**: Add a microphone button to the Steam Virtual Keyboard.
- **Mechanism**: `MutationObserver` watching `document.body`.
- **Target**: Look for the Virtual Keyboard DOM element (e.g., `.VirtualKeyboard`, `.KeyboardWrapper`).
- **Action**:
  - When keyboard appears, append a React Portal or raw DOM element (Mic Button).
  - Button click triggers `SpeechToTextService.start()`.
  - Handle focus management (ensure clicking the button doesn't dismiss the keyboard).

## 4. User Experience Flow
1. **First Run**: User opens plugin menu. "Model missing" status shown. User clicks "Download Model".
2. **Usage**:
   - User opens Steam Keyboard (X button).
   - User sees new Microphone icon on the keyboard.
   - User toggles Microphone.
   - **Overlay**: A small overlay appears showing "Listening..." and live text.
   - User stops speaking (or toggles off).
   - Text is inserted into the active input field.

## 5. Technical Challenges & Solutions
- **Microphone Selection**: `sounddevice` might need to pick the correct default device (PulseAudio default).
- **Permissions**: Backend runs as root, bypassing browser permission prompts.
- **Keyboard DOM Stability**: Steam UI updates might break selectors. We will use robust selectors and error handling.