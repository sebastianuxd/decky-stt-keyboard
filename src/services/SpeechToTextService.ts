export interface SpeechRecognitionResult {
  transcript: string;
  confidence: number;
  isFinal: boolean;
}

export interface SpeechRecognitionError {
  error: string;
  message: string;
}

// Extend Window interface for Web Speech API
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

export class SpeechToTextService {
  private recognition: any;
  private isListening: boolean = false;
  private onResultCallback?: (result: SpeechRecognitionResult) => void;
  private onErrorCallback?: (error: SpeechRecognitionError) => void;
  private onEndCallback?: () => void;

  constructor() {
    // Check if Speech Recognition API is available
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      console.error("Speech Recognition API not available");
      return;
    }

    this.recognition = new SpeechRecognition();
    this.setupRecognition();
  }

  private setupRecognition() {
    if (!this.recognition) return;

    // Configure recognition
    this.recognition.continuous = true;
    this.recognition.interimResults = true;
    this.recognition.maxAlternatives = 1;

    // Handle results
    this.recognition.onresult = (event: any) => {
      const results = event.results;
      const lastResult = results[results.length - 1];
      const transcript = lastResult[0].transcript;
      const confidence = lastResult[0].confidence;
      const isFinal = lastResult.isFinal;

      if (this.onResultCallback) {
        this.onResultCallback({
          transcript,
          confidence,
          isFinal,
        });
      }
    };

    // Handle errors
    this.recognition.onerror = (event: any) => {
      console.error("Speech recognition error:", event.error);
      
      if (this.onErrorCallback) {
        this.onErrorCallback({
          error: event.error,
          message: this.getErrorMessage(event.error),
        });
      }
    };

    // Handle end
    this.recognition.onend = () => {
      this.isListening = false;
      
      if (this.onEndCallback) {
        this.onEndCallback();
      }
    };

    // Handle start
    this.recognition.onstart = () => {
      this.isListening = true;
      console.log("Speech recognition started");
    };
  }

  private getErrorMessage(error: string): string {
    const errorMessages: { [key: string]: string } = {
      "no-speech": "No speech detected. Please try again.",
      "audio-capture": "No microphone found. Please ensure your microphone is connected.",
      "not-allowed": "Microphone access denied. Please grant permission.",
      "network": "Network error occurred. Please check your connection.",
      "aborted": "Speech recognition was aborted.",
    };

    return errorMessages[error] || "An unknown error occurred.";
  }

  public start(language: string = "en-US"): void {
    if (!this.recognition) {
      console.error("Speech Recognition not initialized");
      return;
    }

    if (this.isListening) {
      console.warn("Speech recognition already running");
      return;
    }

    this.recognition.lang = language;
    
    try {
      this.recognition.start();
    } catch (error) {
      console.error("Error starting speech recognition:", error);
    }
  }

  public stop(): void {
    if (!this.recognition || !this.isListening) return;

    try {
      this.recognition.stop();
    } catch (error) {
      console.error("Error stopping speech recognition:", error);
    }
  }

  public abort(): void {
    if (!this.recognition) return;

    try {
      this.recognition.abort();
      this.isListening = false;
    } catch (error) {
      console.error("Error aborting speech recognition:", error);
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

  public isSupported(): boolean {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  public getIsListening(): boolean {
    return this.isListening;
  }

  public cleanup(): void {
    if (this.recognition && this.isListening) {
      this.abort();
    }
    
    this.onResultCallback = undefined;
    this.onErrorCallback = undefined;
    this.onEndCallback = undefined;
  }
}