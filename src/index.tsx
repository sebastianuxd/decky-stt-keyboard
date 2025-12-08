import {
  definePlugin,
  PanelSection,
  PanelSectionRow,
  ServerAPI,
  staticClasses,
  ButtonItem,
} from "decky-frontend-lib";
import React, { VFC, useState, useEffect } from "react";
import { FaMicrophone, FaCopy, FaCheck, FaTrash } from "react-icons/fa";
import { SpeechToTextService, SpeechRecognitionResult, ModelStatus } from "./services/SpeechToTextService";

const Content: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [sttService] = useState(() => new SpeechToTextService(serverAPI));
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);

  useEffect(() => {
    // Check model status on mount
    const checkModel = async () => {
      const status = await sttService.getModelStatus();
      setModelStatus(status);
    };
    checkModel();

    // Set up callbacks
    sttService.onResult((result: SpeechRecognitionResult) => {
      if (result.isFinal) {
        setTranscript((prev) => (prev ? prev + " " : "") + result.transcript);
        setInterimTranscript("");
      } else {
        setInterimTranscript(result.transcript);
      }
    });

    sttService.onError((err) => {
      setError(err.message);
      setIsListening(false);
    });

    sttService.onEnd(() => {
      setIsListening(false);
    });

    sttService.onDownloadProgress((progress: number) => {
      setDownloadProgress(progress);
    });

    return () => {
      sttService.cleanup();
    };
  }, [sttService]);

  const handleDownloadModel = async () => {
    setIsDownloading(true);
    setError(null);
    const success = await sttService.downloadModel();
    setIsDownloading(false);

    if (success) {
      const status = await sttService.getModelStatus();
      setModelStatus(status);
    } else {
      setError("Failed to download model.");
    }
  };

  const handleToggleRecording = async () => {
    if (isListening) {
      sttService.stop();
      setIsListening(false);
    } else {
      if (!modelStatus?.downloaded) {
        setError("Please download the speech model first.");
        return;
      }
      setError(null);
      await sttService.start("en-US");
      setIsListening(true);
    }
  };

  const handleCopy = () => {
    const textToCopy = transcript.trim();
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }).catch((err) => {
        console.error("Failed to copy:", err);
        setError("Failed to copy to clipboard");
      });
    }
  };

  const handleClear = () => {
    setTranscript("");
    setInterimTranscript("");
  };

  const fullText = transcript + (interimTranscript ? " " + interimTranscript : "");

  return (
    <PanelSection>
      {/* Model download prompt */}
      {!modelStatus?.downloaded && (
        <PanelSectionRow>
          <div style={downloadPromptStyle}>
            <p style={{ margin: "0 0 8px 0", fontWeight: "bold" }}>Speech Model Required</p>
            <p style={{ margin: "0 0 12px 0", fontSize: "0.85em", opacity: 0.8 }}>
              Download the offline model (~40MB) to enable speech recognition.
            </p>
            <button
              onClick={handleDownloadModel}
              style={downloadButtonStyle}
              disabled={isDownloading}
            >
              {isDownloading ? `Downloading... ${downloadProgress.toFixed(0)}%` : "Download Model"}
            </button>
          </div>
        </PanelSectionRow>
      )}

      {/* Error display */}
      {error && (
        <PanelSectionRow>
          <div style={errorStyle}>{error}</div>
        </PanelSectionRow>
      )}

      {/* Transcript preview */}
      <PanelSectionRow>
        <div style={transcriptBoxStyle}>
          {fullText ? (
            <>
              <span style={{ color: "#fff" }}>{transcript}</span>
              {interimTranscript && (
                <span style={{ color: "#888", fontStyle: "italic" }}> {interimTranscript}</span>
              )}
            </>
          ) : (
            <span style={{ color: "#666" }}>
              {isListening ? "Listening..." : "Tap the microphone to start speaking"}
            </span>
          )}
        </div>
      </PanelSectionRow>

      {/* Control buttons */}
      <PanelSectionRow>
        <div style={controlsContainerStyle}>
          {/* Mic button */}
          <button
            onClick={handleToggleRecording}
            style={{
              ...micButtonStyle,
              backgroundColor: isListening ? "#e74c3c" : "#2ecc71",
            }}
            disabled={!modelStatus?.downloaded || isDownloading}
          >
            <FaMicrophone size={28} />
          </button>

          {/* Copy button */}
          <button
            onClick={handleCopy}
            style={{
              ...actionButtonStyle,
              opacity: transcript ? 1 : 0.5,
            }}
            disabled={!transcript}
          >
            {copied ? <FaCheck size={20} /> : <FaCopy size={20} />}
          </button>

          {/* Clear button */}
          <button
            onClick={handleClear}
            style={{
              ...actionButtonStyle,
              opacity: transcript || interimTranscript ? 1 : 0.5,
            }}
            disabled={!transcript && !interimTranscript}
          >
            <FaTrash size={18} />
          </button>
        </div>
      </PanelSectionRow>

      {/* Status hint */}
      <PanelSectionRow>
        <div style={hintStyle}>
          {isListening ? "🔴 Recording... tap mic to stop" : "🎤 Tap mic to start"}
        </div>
      </PanelSectionRow>
    </PanelSection>
  );
};

// Styles
const downloadPromptStyle: React.CSSProperties = {
  backgroundColor: "#f39c12",
  color: "#fff",
  padding: "12px",
  borderRadius: "8px",
  textAlign: "center",
  width: "100%",
};

const downloadButtonStyle: React.CSSProperties = {
  backgroundColor: "#fff",
  color: "#f39c12",
  border: "none",
  padding: "8px 20px",
  borderRadius: "6px",
  fontSize: "0.95em",
  fontWeight: "bold",
  cursor: "pointer",
};

const errorStyle: React.CSSProperties = {
  backgroundColor: "#e74c3c",
  color: "#fff",
  padding: "10px",
  borderRadius: "6px",
  textAlign: "center",
  width: "100%",
};

const transcriptBoxStyle: React.CSSProperties = {
  backgroundColor: "#0d1117",
  border: "1px solid #333",
  borderRadius: "8px",
  padding: "12px",
  minHeight: "80px",
  maxHeight: "200px",
  overflowY: "auto",
  fontSize: "0.95em",
  lineHeight: "1.5",
  width: "100%",
};

const controlsContainerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  gap: "16px",
  width: "100%",
  padding: "8px 0",
};

const micButtonStyle: React.CSSProperties = {
  width: "64px",
  height: "64px",
  borderRadius: "50%",
  border: "none",
  color: "#fff",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  cursor: "pointer",
  boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
  transition: "all 0.2s ease",
};

const actionButtonStyle: React.CSSProperties = {
  width: "48px",
  height: "48px",
  borderRadius: "50%",
  border: "none",
  backgroundColor: "#555",
  color: "#fff",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  cursor: "pointer",
  transition: "all 0.2s ease",
};

const hintStyle: React.CSSProperties = {
  textAlign: "center",
  fontSize: "0.85em",
  color: "#888",
  width: "100%",
};

export default definePlugin((serverApi: ServerAPI) => {
  console.log("STT Keyboard plugin loaded");

  return {
    title: <div className={staticClasses.Title}>STT Keyboard</div>,
    content: <Content serverAPI={serverApi} />,
    icon: <FaMicrophone />,
    onDismount() {
      console.log("STT Keyboard plugin dismounted");
    },
  };
});