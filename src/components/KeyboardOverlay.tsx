import React, { VFC, useState, useEffect } from "react";
import { SpeechToTextService, SpeechRecognitionResult, SpeechRecognitionError } from "../services/SpeechToTextService";

interface KeyboardOverlayProps {
  onClose: () => void;
  autoSubmit: boolean;
  language: string;
}

export const KeyboardOverlay: VFC<KeyboardOverlayProps> = ({ onClose, autoSubmit, language }) => {
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sttService] = useState(() => new SpeechToTextService());

  useEffect(() => {
    if (!sttService.isSupported()) {
      setError("Speech recognition is not supported in this browser");
      return;
    }

    sttService.onResult((result: SpeechRecognitionResult) => {
      if (result.isFinal) {
        setTranscript((prev) => prev + " " + result.transcript);
        setInterimTranscript("");
        
        if (autoSubmit) {
          handleSubmit(transcript + " " + result.transcript);
        }
      } else {
        setInterimTranscript(result.transcript);
      }
    });

    sttService.onError((error: SpeechRecognitionError) => {
      setError(error.message);
      setIsListening(false);
    });

    sttService.onEnd(() => {
      setIsListening(false);
    });

    return () => {
      sttService.cleanup();
    };
  }, [sttService, autoSubmit, transcript]);

  const handleStart = () => {
    setError(null);
    sttService.start(language);
    setIsListening(true);
  };

  const handleStop = () => {
    sttService.stop();
    setIsListening(false);
  };

  const handleSubmit = (text?: string) => {
    const finalText = text || transcript.trim();
    if (finalText) {
      // Insert text into active input field
      insertTextIntoActiveElement(finalText);
    }
    onClose();
  };

  const handleClear = () => {
    setTranscript("");
    setInterimTranscript("");
    setError(null);
  };

  const insertTextIntoActiveElement = (text: string) => {
    const activeElement = document.activeElement as HTMLInputElement | HTMLTextAreaElement;
    
    if (activeElement && (activeElement.tagName === "INPUT" || activeElement.tagName === "TEXTAREA")) {
      const startPos = activeElement.selectionStart || 0;
      const endPos = activeElement.selectionEnd || 0;
      const value = activeElement.value;
      
      activeElement.value = value.substring(0, startPos) + text + value.substring(endPos);
      activeElement.selectionStart = activeElement.selectionEnd = startPos + text.length;
      
      // Trigger input event
      const event = new Event("input", { bubbles: true });
      activeElement.dispatchEvent(event);
    } else {
      // Fallback: copy to clipboard
      navigator.clipboard.writeText(text).then(() => {
        console.log("Text copied to clipboard:", text);
      });
    }
  };

  return (
    <div style={overlayStyle}>
      <div style={modalStyle}>
        <div style={headerStyle}>
          <h2 style={{ margin: 0, fontSize: "1.5em" }}>Speech-to-Text</h2>
          <button onClick={onClose} style={closeButtonStyle}>×</button>
        </div>
        
        <div style={contentStyle}>
          {error && (
            <div style={errorStyle}>
              {error}
            </div>
          )}
          
          <div style={transcriptBoxStyle}>
            <div style={{ minHeight: "100px" }}>
              {transcript && <span style={{ color: "#fff" }}>{transcript}</span>}
              {interimTranscript && <span style={{ color: "#aaa", fontStyle: "italic" }}> {interimTranscript}</span>}
              {!transcript && !interimTranscript && (
                <span style={{ color: "#666" }}>Click the microphone to start speaking...</span>
              )}
            </div>
          </div>

          <div style={controlsStyle}>
            <button
              onClick={isListening ? handleStop : handleStart}
              style={{
                ...micButtonStyle,
                backgroundColor: isListening ? "#e74c3c" : "#3498db",
              }}
              disabled={!!error && error.includes("not supported")}
            >
              {isListening ? "⏹ Stop" : "🎤 Start"}
            </button>
            
            <button onClick={handleClear} style={actionButtonStyle}>
              Clear
            </button>
            
            <button 
              onClick={() => handleSubmit()} 
              style={{...actionButtonStyle, backgroundColor: "#27ae60"}}
              disabled={!transcript.trim()}
            >
              Submit
            </button>
          </div>

          <div style={infoStyle}>
            Language: {language} | {isListening ? "Listening..." : "Ready"}
          </div>
        </div>
      </div>
    </div>
  );
};

// Styles
const overlayStyle: React.CSSProperties = {
  position: "fixed",
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: "rgba(0, 0, 0, 0.8)",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  zIndex: 10000,
};

const modalStyle: React.CSSProperties = {
  backgroundColor: "#1a1a1a",
  borderRadius: "10px",
  padding: "0",
  maxWidth: "600px",
  width: "90%",
  boxShadow: "0 4px 20px rgba(0, 0, 0, 0.5)",
  border: "1px solid #333",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "20px",
  borderBottom: "1px solid #333",
  color: "#fff",
};

const closeButtonStyle: React.CSSProperties = {
  background: "none",
  border: "none",
  fontSize: "2em",
  color: "#fff",
  cursor: "pointer",
  padding: "0",
  width: "40px",
  height: "40px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};

const contentStyle: React.CSSProperties = {
  padding: "20px",
};

const errorStyle: React.CSSProperties = {
  backgroundColor: "#e74c3c",
  color: "#fff",
  padding: "10px",
  borderRadius: "5px",
  marginBottom: "15px",
};

const transcriptBoxStyle: React.CSSProperties = {
  backgroundColor: "#0d1117",
  border: "1px solid #333",
  borderRadius: "5px",
  padding: "15px",
  marginBottom: "15px",
  minHeight: "120px",
  maxHeight: "300px",
  overflowY: "auto",
  fontSize: "1.1em",
  lineHeight: "1.6",
};

const controlsStyle: React.CSSProperties = {
  display: "flex",
  gap: "10px",
  marginBottom: "15px",
};

const micButtonStyle: React.CSSProperties = {
  flex: 2,
  padding: "15px",
  fontSize: "1.2em",
  border: "none",
  borderRadius: "5px",
  cursor: "pointer",
  color: "#fff",
  fontWeight: "bold",
  transition: "all 0.3s",
};

const actionButtonStyle: React.CSSProperties = {
  flex: 1,
  padding: "15px",
  fontSize: "1em",
  border: "none",
  borderRadius: "5px",
  cursor: "pointer",
  backgroundColor: "#555",
  color: "#fff",
  fontWeight: "bold",
  transition: "all 0.3s",
};

const infoStyle: React.CSSProperties = {
  textAlign: "center",
  color: "#888",
  fontSize: "0.9em",
};