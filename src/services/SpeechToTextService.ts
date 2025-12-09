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
  private readonly POLL_INTERVAL_MS = 100; // Poll every 100ms for better responsiveness

  constructor(serverAPI: ServerAPI) {
    this.serverAPI = serverAPI;
    this.setupEventListeners();
  }

  private setupEventListeners() {
    // Listen for STT events from backend
    this.listeners["stt_result"] = (data: any) => {
      // Handle CustomEvent
      if (data && data.detail) data = data.detail;

      // Reset silence timer on any activity
      this.resetSilenceTimer();

      if (this.onResultCallback && data?.result) {
        this.onResultCallback({
          transcript: data.result,
          confidence: data.final ? 1.0 : 0.5,
          isFinal: data.final,
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
      console.log("STT started");
      this.isListening = true;
    };

    this.listeners["stt_stopped"] = (data: any) => {
      console.log("STT stopped");
      this.isListening = false;
      if (this.onEndCallback) {
        this.onEndCallback();
      }
    };

    this.listeners["download_progress"] = (data: any) => {
      // Handle CustomEvent
      if (data && data.detail) data = data.detail;

      console.log("Model download progress:", data?.percent);
      if (this.onDownloadProgressCallback) {
        this.onDownloadProgressCallback(data?.percent || 0);
      }
    };

    // Register all listeners
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
    console.log("[SpeechToTextService] start() called");

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

      if (!result.success) {
        console.error("[SpeechToTextService] Backend call failed:", result);
        throw new Error((result.result as any)?.error || "Failed to start STT");
      }

      this.isListening = true;

      // Start polling for results since events may not be reliable
      this.startPolling();
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

  private startPolling(): void {
    if (this.pollInterval) return;

    console.log("[SpeechToTextService] Starting polling for results...");
    this.pollInterval = window.setInterval(async () => {
      try {
        const response = await this.serverAPI.callPluginMethod<{}, { results: Array<{ result: string; final: boolean }>; is_recording: boolean }>(
          "get_pending_results",
          {}
        );

        if (response.success && response.result?.results) {
          for (const item of response.result.results) {
            if (this.onResultCallback && item.result) {
              this.onResultCallback({
                transcript: item.result,
                confidence: item.final ? 1.0 : 0.5,
                isFinal: item.final,
              });
            }
          }
        }

        // Stop polling if no longer recording
        if (response.success && !response.result?.is_recording && !this.isListening) {
          this.stopPolling();
        }
      } catch (e) {
        console.error("[SpeechToTextService] Polling error:", e);
      }
    }, this.POLL_INTERVAL_MS);
  }

  private stopPolling(): void {
    if (this.pollInterval) {
      console.log("[SpeechToTextService] Stopping polling");
      window.clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  public async stop(): Promise<void> {
    if (!this.isListening) return;

    this.isListening = false;
    this.stopPolling();

    try {
      await this.serverAPI.callPluginMethod("stop_stt", {});
    } catch (error) {
      console.error("Error stopping speech recognition:", error);
    }

    if (this.onEndCallback) {
      this.onEndCallback();
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