export class SettingsManager {
  private static STORAGE_KEY = "decky-stt-keyboard-settings";
  private static settings: Map<string, any> = new Map();
  private static initialized = false;

  private static initialize() {
    if (this.initialized) return;

    try {
      const stored = localStorage.getItem(this.STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        Object.entries(parsed).forEach(([key, value]) => {
          this.settings.set(key, value);
        });
      }
    } catch (error) {
      console.error("Error loading settings:", error);
    }

    this.initialized = true;
  }

  public static getSetting<T>(key: string, defaultValue: T): T {
    this.initialize();
    return this.settings.has(key) ? this.settings.get(key) : defaultValue;
  }

  public static setSetting(key: string, value: any): void {
    this.initialize();
    this.settings.set(key, value);
    this.saveSettings();
  }

  public static deleteSetting(key: string): void {
    this.initialize();
    this.settings.delete(key);
    this.saveSettings();
  }

  public static getAllSettings(): Record<string, any> {
    this.initialize();
    const result: Record<string, any> = {};
    this.settings.forEach((value, key) => {
      result[key] = value;
    });
    return result;
  }

  private static saveSettings(): void {
    try {
      const settingsObject: Record<string, any> = {};
      this.settings.forEach((value, key) => {
        settingsObject[key] = value;
      });
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(settingsObject));
    } catch (error) {
      console.error("Error saving settings:", error);
    }
  }

  public static reset(): void {
    this.settings.clear();
    try {
      localStorage.removeItem(this.STORAGE_KEY);
    } catch (error) {
      console.error("Error resetting settings:", error);
    }
  }
}