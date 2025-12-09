import {
  definePlugin,
  PanelSection,
  PanelSectionRow,
  ServerAPI,
  staticClasses,
  ButtonItem,
  TextField,
} from "decky-frontend-lib";
import React, { VFC, useState, useEffect, useRef } from "react";
import { FaMicrophone } from "react-icons/fa";
import { SpeechToTextService, SpeechRecognitionResult, ModelStatus } from "./services/SpeechToTextService";

const Content: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
  const [transcript, setTranscript] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [sttService] = useState(() => new SpeechToTextService(serverAPI));
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [interimTranscript, setInterimTranscript] = useState("");
  // Track both cursor position and selection end for text replacement
  const [selectionStart, setSelectionStart] = useState<number>(0);
  const [selectionEnd, setSelectionEnd] = useState<number>(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
        // Clear interim
        setInterimTranscript("");

        // Insert new transcription at cursor position or replace selection
        setTranscript((prev) => {
          const before = prev.slice(0, selectionStart);
          const after = prev.slice(selectionEnd); // Use selectionEnd to replace selected text
          const newText = result.transcript.trim();
          const spaceBefore = before.length > 0 && !before.endsWith(" ") ? " " : "";
          const spaceAfter = after.length > 0 && !after.startsWith(" ") ? " " : "";
          const newTranscript = before + spaceBefore + newText + spaceAfter + after;
          // Update cursor position to after the inserted text
          const newCursorPos = before.length + spaceBefore.length + newText.length;
          setSelectionStart(newCursorPos);
          setSelectionEnd(newCursorPos);
          return newTranscript;
        });
      } else {
        // Update partial result
        setInterimTranscript(result.transcript);
      }
    });

    sttService.onError((err) => {
      setError(err.message);
      setIsListening(false);
      setInterimTranscript("");
    });

    sttService.onEnd(() => {
      setIsListening(false);
      setInterimTranscript("");
    });

    sttService.onDownloadProgress((progress: number) => {
      setDownloadProgress(progress);
    });

    return () => {
      sttService.cleanup();
    };
  }, [sttService, selectionStart, selectionEnd]);

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

  const handleCopy = async () => {
    const textToCopy = transcript.trim();
    if (!textToCopy) return;

    // Use the same approach as decky-lsfg-vk: temporary input with document.execCommand
    const tempInput = document.createElement('input');
    tempInput.value = textToCopy;
    tempInput.style.position = 'absolute';
    tempInput.style.left = '-9999px';
    document.body.appendChild(tempInput);

    try {
      tempInput.focus();
      tempInput.select();

      let copySuccess = false;
      try {
        // Use execCommand as primary method (works in gaming mode)
        if (document.execCommand('copy')) {
          copySuccess = true;
        }
      } catch (e) {
        console.warn("execCommand failed:", e);
      }

      // If frontend method worked, we're done
      if (copySuccess) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        return;
      }

      // Fallback to backend method if frontend failed
      console.log("Frontend copy failed, trying backend...");
      const result = await serverAPI.callPluginMethod<{ text: string }, { success: boolean; error?: string }>(
        "copy_to_clipboard",
        { text: textToCopy }
      );
      if (result.success && result.result?.success) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } else {
        setError("Copy failed - try manually selecting and copying");
      }
    } catch (err) {
      console.error("Failed to copy:", err);
      setError("Copy failed");
    } finally {
      document.body.removeChild(tempInput);
    }
  };

  const handleClear = () => {
    setTranscript("");
    setSelectionStart(0);
    setSelectionEnd(0);
  };

  // Handle text changes from the editable textarea
  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setTranscript(e.target.value);
  };

  // Track cursor/selection position when user interacts with textarea
  const handleSelectionChange = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    const target = e.target as HTMLTextAreaElement;
    setSelectionStart(target.selectionStart || 0);
    setSelectionEnd(target.selectionEnd || 0);
  };

  // Save selection when textarea loses focus (so clicking button doesn't lose it)
  const handleBlur = (e: React.FocusEvent<HTMLTextAreaElement>) => {
    setSelectionStart(e.target.selectionStart || 0);
    setSelectionEnd(e.target.selectionEnd || 0);
  };

  return (
    <PanelSection>
      {/* Model download prompt */}
      {!modelStatus?.downloaded && (
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            label={isDownloading ? `Downloading... ${downloadProgress.toFixed(0)}%` : "Download Speech Model"}
            onClick={handleDownloadModel}
            disabled={isDownloading}
            description="Download the offline model (~40MB) to enable speech recognition."
          />
        </PanelSectionRow>
      )}

      {/* Error display */}
      {error && (
        <PanelSectionRow>
          <div style={errorStyle}>{error}</div>
        </PanelSectionRow>
      )}

      {/* Editable transcript area */}
      <PanelSectionRow>
        <textarea
          ref={textareaRef}
          value={transcript}
          onChange={handleTextChange}
          onClick={handleSelectionChange}
          onKeyUp={handleSelectionChange}
          onSelect={handleSelectionChange}
          onBlur={handleBlur}
          placeholder={isListening ? "Listening..." : "Press Start Recording to begin, or type here"}
          style={transcriptBoxStyle}
          disabled={isListening}
        />
      </PanelSectionRow>

      {/* Interim transcript display */}
      {(interimTranscript || isListening) && (
        <PanelSectionRow>
          <div style={{
            ...transcriptBoxStyle,
            minHeight: "30px",
            color: "#aaa",
            fontStyle: "italic",
            fontSize: "0.9em",
            marginTop: "-10px",
            borderTop: "none",
            borderTopLeftRadius: "0",
            borderTopRightRadius: "0"
          }}>
            {interimTranscript || "..."}
          </div>
        </PanelSectionRow>
      )}

      {/* Recording button */}
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          label={isListening ? "🔴 Stop Recording" : "🎤 Start Recording"}
          onClick={handleToggleRecording}
          disabled={!modelStatus?.downloaded || isDownloading}
        />
      </PanelSectionRow>

      {/* Copy button */}
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          label={copied ? "✓ Copied!" : "📋 Copy to Clipboard"}
          onClick={handleCopy}
          disabled={!transcript}
        />
      </PanelSectionRow>

      {/* Clear button */}
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          label="🗑️ Clear Text"
          onClick={handleClear}
          disabled={!transcript}
        />
      </PanelSectionRow>

      {/* Status hint */}
      <PanelSectionRow>
        <div style={hintStyle}>
          {isListening ? "🔴 Recording in progress..." : "🎤 Ready to record"}
        </div>
      </PanelSectionRow>
    </PanelSection>
  );
};

// Styles
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
  color: "#fff",
  resize: "vertical",
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