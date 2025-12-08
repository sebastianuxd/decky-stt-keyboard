import { ServerAPI } from "decky-frontend-lib";

export interface SpeechRecognitionResult {
  transcript: string;
  confidence: number;
  isFinal: boolean;
}

export interface SpeechRecognitionError {
  error: string;
  message: string;
}

export interface ModelStatus {
  downloaded: boolean;
  path: string;
  name: string;
}

export class SpeechToTextService {
  private serverAPI: ServerAPI;
  private isListening: boolean = false;
  private onResultCallback?: (result: SpeechRecognitionResult) => void;
  private onErrorCallback?: (error: SpeechRecognitionError) => void;
  private onEndCallback?: () => void;
  private onDownloadProgressCallback?: (progress: number) => void;
  private listeners: { [key: string]: (data: any) => void } = {};
  private pollInterval: number | null = null;
  private readonly POLL_INTERVAL_MS = 200; // Poll every 200ms

  constructor(serverAPI: ServerAPI) {
    this.serverAPI = serverAPI;
    this.setupEventListeners();
  }

  private setupEventListeners() {
    // Listen for STT events from backend
    this.listeners["stt_partial"] = (data: any) => {
      // Handle CustomEvent
      if (data && data.detail) data = data.detail;

      // Reset silence timer on any activity
      this.resetSilenceTimer();

      if (this.onResultCallback && data?.text) {
        this.onResultCallback({
          transcript: data.text,
          confidence: 0.5,
          isFinal: false,
        });
      }
    };

    this.listeners["stt_final"] = (data: any) => {
      // Handle CustomEvent
      if (data && data.detail) data = data.detail;

      // Reset silence timer on any activity
      this.resetSilenceTimer();

      if (this.onResultCallback && data?.text) {
        this.onResultCallback({
          transcript: data.text,
          confidence: 1.0,
          isFinal: true,
        });
      }
    };

    this.listeners["stt_error"] = (data: any) => {
      // Handle CustomEvent
      if (data && data.detail) data = data.detail;

      console.error("STT error from backend:", data?.error);
      if (this.onErrorCallback) {
        this.onErrorCallback({
          error: "backend-error",
          message: data?.error || "Unknown error occurred",
        });
      }
      this.isListening = false;
    };

    this.listeners["stt_started"] = (data: any) => {
      // Handle CustomEvent
      if (data && data.detail) data = data.detail;

      console.log("STT started:", data);
      this.isListening = true;
    };

    this.listeners["stt_stopped"] = (data: any) => {
      // Handle CustomEvent
      if (data && data.detail) data = data.detail;

      console.log("STT stopped:", data);
      this.isListening = false;
      if (this.onEndCallback) {
        this.onEndCallback();
      }
    };

    this.listeners["stt_download_progress"] = (data: any) => {
      // Handle CustomEvent
      if (data && data.detail) data = data.detail;

      console.log("Model download progress:", data?.percent);
      if (this.onDownloadProgressCallback) {
        this.onDownloadProgressCallback(data?.percent || 0);
      }
    };

    this.listeners["stt_download_complete"] = (data: any) => {
      // Handle CustomEvent
      if (data && data.detail) data = data.detail;

      console.log("Model download complete:", data);
    };

    // Register all listeners
    // Try window.DeckyPlugin (legacy), check for other globals, or fallback to window
    const win = window as any;
    const eventBus = win.DeckyPlugin || win;

    console.log("[SpeechToTextService] Registering events on:", eventBus === win ? "window" : "DeckyPlugin");

    Object.entries(this.listeners).forEach(([event, handler]) => {
      try {
        eventBus.addEventListener(event, handler);
      } catch (e) {
        console.error(`Failed to add listener for ${event}:`, e);
      }
    });
  }

  public async start(language: string = "en-US"): Promise<void> {
    console.log("[SpeechToTextService] start() called with language:", language);

    if (this.isListening) {
      console.warn("[SpeechToTextService] Speech recognition already running");
      return;
    }

    try {
      console.log("[SpeechToTextService] Calling backend start_stt...");
      const result = await this.serverAPI.callPluginMethod<{ language: string }, { success: boolean; error?: string }>(
        "start_stt",
        { language }
      );

      console.log("[SpeechToTextService] Backend response:", JSON.stringify(result));

      if (!result.success) {
        console.error("[SpeechToTextService] Backend call failed:", result);
        throw new Error((result.result as any)?.error || "Failed to start STT");
      }

      // Start polling for transcription results
      this.isListening = true;
      this.startPolling();
      console.log("[SpeechToTextService] Recording started, polling active");
    } catch (error) {
      console.error("[SpeechToTextService] Error starting speech recognition:", error);
      if (this.onErrorCallback) {
        this.onErrorCallback({
          error: "start-failed",
          message: error instanceof Error ? error.message : "Failed to start recording",
        });
      }
    }
  }

  public async stop(): Promise<void> {
    if (!this.isListening) return;

    // Stop polling first
    this.stopPolling();
    this.isListening = false;

    try {
      await this.serverAPI.callPluginMethod("stop_stt", {});
    } catch (error) {
      console.error("Error stopping speech recognition:", error);
    }

    if (this.onEndCallback) {
      this.onEndCallback();
    }
  }

  private startPolling(): void {
    if (this.pollInterval !== null) {
      return; // Already polling
    }

    console.log("[SpeechToTextService] Starting polling for transcriptions");

    this.pollInterval = window.setInterval(async () => {
      try {
        const result = await this.serverAPI.callPluginMethod<{}, { success: boolean; results: Array<{ type: string; text: string; timestamp: number }> }>(
          "get_transcriptions",
          {}
        );

        if (result.success && result.result?.results && result.result.results.length > 0) {
          for (const item of result.result.results) {
            // Reset silence timer on any activity
            this.resetSilenceTimer();

            if (this.onResultCallback) {
              this.onResultCallback({
                transcript: item.text,
                confidence: item.type === "final" ? 1.0 : 0.5,
                isFinal: item.type === "final"
              });
            }
          }
        }
      } catch (error) {
        console.error("Error polling transcriptions:", error);
      }
    }, this.POLL_INTERVAL_MS);
  }

  private stopPolling(): void {
    if (this.pollInterval !== null) {
      console.log("[SpeechToTextService] Stopping polling");
      window.clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  public abort(): void {
    // For backend-based STT, abort is the same as stop
    this.stop();
  }

  public async getModelStatus(): Promise<ModelStatus | null> {
    try {
      const result = await this.serverAPI.callPluginMethod<{}, ModelStatus>("get_model_status", {});
      return result.success ? result.result : null;
    } catch (error) {
      console.error("Error getting model status:", error);
      return null;
    }
  }

  public async downloadModel(): Promise<boolean> {
    try {
      console.log("SpeechToTextService: Calling download_model backend method...");
      const result = await this.serverAPI.callPluginMethod<{}, { success: boolean; error?: string }>(
        "download_model",
        {}
      );
      console.log("SpeechToTextService: download_model result:", result);

      if (!result.success) {
        console.error("SpeechToTextService: Backend call failed:", result);
        return false;
      }

      if (!result.result?.success) {
        console.error("SpeechToTextService: Backend returned failure:", result.result?.error);
        return false;
      }

      return true;
    } catch (error) {
      console.error("Error downloading model:", error);
      return false;
    }
  }

  public async getMicrophoneStatus(): Promise<any> {
    try {
      const result = await this.serverAPI.callPluginMethod("get_microphone_status", {});
      return result.success ? result.result : null;
    } catch (error) {
      console.error("Error getting microphone status:", error);
      return null;
    }
  }

  public onResult(callback: (result: SpeechRecognitionResult) => void): void {
    this.onResultCallback = callback;
  }

  public onError(callback: (error: SpeechRecognitionError) => void): void {
    this.onErrorCallback = callback;
  }

  public onEnd(callback: () => void): void {
    this.onEndCallback = callback;
  }

  public onDownloadProgress(callback: (progress: number) => void): void {
    this.onDownloadProgressCallback = callback;
  }

  public isSupported(): boolean {
    // Backend-based STT is always supported
    return true;
  }

  public getIsListening(): boolean {
    return this.isListening;
  }

  private silenceTimer: number | null = null;
  private silenceTimeoutMs: number = 2000;

  private resetSilenceTimer() {
    if (this.silenceTimer) {
      window.clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }

    // Only set timer if in "smart" mode (checked by caller or we store mode here?)
    // Checks should happen where mode is managed or we can store it here.
    // For now, let's expose a method to enable/disable smart mode or just check a flag
    if (this.isSmartMode) {
      this.silenceTimer = window.setTimeout(() => {
        console.log("Silence detected, stopping recording...");
        this.stop();
      }, this.silenceTimeoutMs);
    }
  }

  public setSmartMode(enabled: boolean) {
    this.isSmartMode = enabled;
  }

  private isSmartMode: boolean = false;

  public cleanup(): void {
    if (this.silenceTimer) {
      window.clearTimeout(this.silenceTimer);
    }
    if (this.isListening) {
      this.stop();
    }

    // Remove all listeners
    const win = window as any;
    const eventBus = win.DeckyPlugin || win;

    Object.entries(this.listeners).forEach(([event, handler]) => {
      try {
        eventBus.removeEventListener(event, handler);
      } catch (e) {
        console.error(`Failed to remove listener for ${event}:`, e);
      }
    });

    this.onResultCallback = undefined;
    this.onErrorCallback = undefined;
    this.onEndCallback = undefined;
    this.onDownloadProgressCallback = undefined;
  }
}