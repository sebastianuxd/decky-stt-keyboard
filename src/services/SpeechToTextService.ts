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

  constructor(serverAPI: ServerAPI) {
    this.serverAPI = serverAPI;
    this.setupEventListeners();
  }

  private setupEventListeners() {
    // Listen for STT events from backend
    this.listeners["stt_partial"] = (data: any) => {
      if (this.onResultCallback && data?.text) {
        this.onResultCallback({
          transcript: data.text,
          confidence: 0.5,
          isFinal: false,
        });
      }
    };

    this.listeners["stt_final"] = (data: any) => {
      if (this.onResultCallback && data?.text) {
        this.onResultCallback({
          transcript: data.text,
          confidence: 1.0,
          isFinal: true,
        });
      }
    };

    this.listeners["stt_error"] = (data: any) => {
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
      console.log("STT started:", data);
      this.isListening = true;
    };

    this.listeners["stt_stopped"] = (data: any) => {
      console.log("STT stopped:", data);
      this.isListening = false;
      if (this.onEndCallback) {
        this.onEndCallback();
      }
    };

    this.listeners["stt_download_progress"] = (data: any) => {
      console.log("Model download progress:", data?.percent);
      if (this.onDownloadProgressCallback) {
        this.onDownloadProgressCallback(data?.percent || 0);
      }
    };

    this.listeners["stt_download_complete"] = (data: any) => {
      console.log("Model download complete:", data);
    };

    // Register all listeners
    const deckyPlugin = (window as any).DeckyPlugin;
    if (deckyPlugin) {
      Object.entries(this.listeners).forEach(([event, handler]) => {
        try {
          deckyPlugin.addEventListener(event, handler);
        } catch (e) {
          console.error(`Failed to add listener for ${event}:`, e);
        }
      });
    } else {
      console.error("DeckyPlugin global not found, cannot register event listeners");
    }
  }

  public async start(language: string = "en-US"): Promise<void> {
    if (this.isListening) {
      console.warn("Speech recognition already running");
      return;
    }

    try {
      const result = await this.serverAPI.callPluginMethod<{ language: string }, { success: boolean; error?: string }>(
        "start_stt",
        { language }
      );

      if (!result.success) {
        throw new Error((result.result as any)?.error || "Failed to start STT");
      }
    } catch (error) {
      console.error("Error starting speech recognition:", error);
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

    try {
      await this.serverAPI.callPluginMethod("stop_stt", {});
    } catch (error) {
      console.error("Error stopping speech recognition:", error);
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

  public cleanup(): void {
    if (this.isListening) {
      this.stop();
    }

    // Remove all listeners
    const deckyPlugin = (window as any).DeckyPlugin;
    if (deckyPlugin) {
      Object.entries(this.listeners).forEach(([event, handler]) => {
        try {
          deckyPlugin.removeEventListener(event, handler);
        } catch (e) {
          console.error(`Failed to remove listener for ${event}:`, e);
        }
      });
    }

    this.onResultCallback = undefined;
    this.onErrorCallback = undefined;
    this.onEndCallback = undefined;
    this.onDownloadProgressCallback = undefined;
  }
}