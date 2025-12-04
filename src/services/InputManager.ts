/**
 * InputManager handles keyboard shortcuts and chord commands for activating STT
 */

export type InputCallback = () => void;

export interface ChordCommand {
  buttons: string[];
  callback: InputCallback;
}

export class InputManager {
  private callbacks: Map<string, InputCallback> = new Map();
  private chordCommands: ChordCommand[] = [];
  private pressedButtons: Set<string> = new Set();
  private keydownHandler: ((e: KeyboardEvent) => void) | null = null;
  private keyupHandler: ((e: KeyboardEvent) => void) | null = null;
  private gamepadCheckInterval: number | null = null;

  constructor() {
    this.initialize();
  }

  private initialize() {
    // Set up keyboard event listeners
    this.keydownHandler = this.handleKeyDown.bind(this);
    this.keyupHandler = this.handleKeyUp.bind(this);

    window.addEventListener('keydown', this.keydownHandler);
    window.addEventListener('keyup', this.keyupHandler);

    // Start checking for gamepad input (for Steam button combos)
    this.startGamepadPolling();
  }

  private handleKeyDown(event: KeyboardEvent) {
    const key = this.normalizeKey(event);
    this.pressedButtons.add(key);

    // Check for registered shortcuts
    const shortcut = this.getShortcutString();
    const callback = this.callbacks.get(shortcut);
    
    if (callback) {
      event.preventDefault();
      event.stopPropagation();
      callback();
    }

    // Check for chord commands
    this.checkChordCommands();
  }

  private handleKeyUp(event: KeyboardEvent) {
    const key = this.normalizeKey(event);
    this.pressedButtons.delete(key);
  }

  private normalizeKey(event: KeyboardEvent): string {
    let key = event.key.toLowerCase();
    
    // Map special keys
    const keyMap: { [key: string]: string } = {
      'control': 'ctrl',
      'meta': 'cmd',
      'escape': 'esc',
      ' ': 'space',
    };

    key = keyMap[key] || key;

    // Build modifier string
    const modifiers: string[] = [];
    if (event.ctrlKey) modifiers.push('ctrl');
    if (event.altKey) modifiers.push('alt');
    if (event.shiftKey) modifiers.push('shift');
    if (event.metaKey) modifiers.push('cmd');

    // Remove duplicate modifier if it's also the key
    const uniqueModifiers = modifiers.filter(m => m !== key);
    
    return uniqueModifiers.length > 0 ? `${uniqueModifiers.join('+')}+${key}` : key;
  }

  private getShortcutString(): string {
    const buttons = Array.from(this.pressedButtons).sort();
    return buttons.join('+');
  }

  private startGamepadPolling() {
    // Poll gamepads for Steam button detection
    this.gamepadCheckInterval = window.setInterval(() => {
      this.checkGamepadInput();
    }, 100);
  }

  private checkGamepadInput() {
    const gamepads = navigator.getGamepads();
    
    for (const gamepad of gamepads) {
      if (!gamepad) continue;

      // Steam Deck typically shows as a standard gamepad
      // Button mappings may vary, but we'll check for common patterns
      
      // Check for Steam button (often mapped to button 16 or guide button)
      // Combined with Y button (button 3)
      const steamButton = gamepad.buttons[16]; // Guide/Steam button
      const yButton = gamepad.buttons[3]; // Y button

      if (steamButton?.pressed && yButton?.pressed) {
        // Add to pressed buttons set
        this.pressedButtons.add('steam');
        this.pressedButtons.add('y');
        this.checkChordCommands();
      } else {
        this.pressedButtons.delete('steam');
        this.pressedButtons.delete('y');
      }
    }
  }

  private checkChordCommands() {
    for (const chord of this.chordCommands) {
      const allPressed = chord.buttons.every(button => 
        this.pressedButtons.has(button.toLowerCase())
      );

      if (allPressed) {
        chord.callback();
        // Clear pressed buttons to prevent repeated activation
        this.pressedButtons.clear();
        break;
      }
    }
  }

  /**
   * Register a keyboard shortcut
   * @param shortcut - Shortcut string (e.g., "ctrl+shift+s")
   * @param callback - Function to call when shortcut is pressed
   */
  public registerShortcut(shortcut: string, callback: InputCallback): void {
    const normalized = shortcut.toLowerCase().split('+').sort().join('+');
    this.callbacks.set(normalized, callback);
    console.log(`Registered shortcut: ${normalized}`);
  }

  /**
   * Unregister a keyboard shortcut
   * @param shortcut - Shortcut string to remove
   */
  public unregisterShortcut(shortcut: string): void {
    const normalized = shortcut.toLowerCase().split('+').sort().join('+');
    this.callbacks.delete(normalized);
    console.log(`Unregistered shortcut: ${normalized}`);
  }

  /**
   * Register a chord command (multiple buttons pressed simultaneously)
   * @param buttons - Array of button names (e.g., ["steam", "y"])
   * @param callback - Function to call when chord is detected
   */
  public registerChordCommand(buttons: string[], callback: InputCallback): void {
    const normalizedButtons = buttons.map(b => b.toLowerCase());
    this.chordCommands.push({
      buttons: normalizedButtons,
      callback,
    });
    console.log(`Registered chord command: ${normalizedButtons.join('+')}`);
  }

  /**
   * Unregister a chord command
   * @param buttons - Array of button names to remove
   */
  public unregisterChordCommand(buttons: string[]): void {
    const normalizedButtons = buttons.map(b => b.toLowerCase());
    this.chordCommands = this.chordCommands.filter(chord => {
      return !this.arraysEqual(chord.buttons, normalizedButtons);
    });
    console.log(`Unregistered chord command: ${normalizedButtons.join('+')}`);
  }

  /**
   * Check if two arrays are equal
   */
  private arraysEqual(arr1: string[], arr2: string[]): boolean {
    if (arr1.length !== arr2.length) return false;
    const sorted1 = [...arr1].sort();
    const sorted2 = [...arr2].sort();
    return sorted1.every((val, idx) => val === sorted2[idx]);
  }

  /**
   * Get all registered shortcuts
   */
  public getRegisteredShortcuts(): string[] {
    return Array.from(this.callbacks.keys());
  }

  /**
   * Get all registered chord commands
   */
  public getRegisteredChords(): string[][] {
    return this.chordCommands.map(chord => chord.buttons);
  }

  /**
   * Clean up event listeners
   */
  public cleanup(): void {
    if (this.keydownHandler) {
      window.removeEventListener('keydown', this.keydownHandler);
    }
    
    if (this.keyupHandler) {
      window.removeEventListener('keyup', this.keyupHandler);
    }

    if (this.gamepadCheckInterval !== null) {
      clearInterval(this.gamepadCheckInterval);
      this.gamepadCheckInterval = null;
    }

    this.callbacks.clear();
    this.chordCommands = [];
    this.pressedButtons.clear();

    console.log('InputManager cleaned up');
  }
}