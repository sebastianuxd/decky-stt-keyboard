console.log("=" + "=".repeat(78) + "=");
console.log("STT KEYBOARD PLUGIN: MODULE SCRIPT EXECUTING");
console.log("=" + "=".repeat(78) + "=");
try {
  // @ts-ignore
  console.log("STT Keyboard: SteamClient available:", !!window.SteamClient);
  // @ts-ignore
  if (window.SteamClient && window.SteamClient.System) {
    // @ts-ignore
    console.log("STT Keyboard: RegisterForOnResumeFromSuspend available:", !!window.SteamClient.System.RegisterForOnResumeFromSuspend);
  }
} catch (e) {
  console.error("STT Keyboard: Error checking SteamClient", e);
}
import {
  definePlugin,
  PanelSection,
  PanelSectionRow,
  ServerAPI,
  staticClasses,
  ToggleField,
  ButtonItem,
} from "decky-frontend-lib";
import React, { VFC, useState } from "react";
import { FaMicrophone } from "react-icons/fa";
import { SpeechToTextService } from "./services/SpeechToTextService";
import { KeyboardOverlay } from "./components/KeyboardOverlay";
import { SettingsManager } from "./services/SettingsManager";
import { InputManager } from "./services/InputManager";

let setOverlayCallback: ((visible: boolean) => void) | null = null;

const Content: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
  const [isEnabled, setIsEnabled] = useState(
    SettingsManager.getSetting("enabled", true)
  );
  const [showOverlay, setShowOverlay] = useState(false);

  // Register the callback to show overlay
  React.useEffect(() => {
    setOverlayCallback = setShowOverlay;
    return () => {
      setOverlayCallback = null;
    };
  }, []);
  const [autoSubmit, setAutoSubmit] = useState(
    SettingsManager.getSetting("autoSubmit", false)
  );
  const [language, setLanguage] = useState(
    SettingsManager.getSetting("language", "en-US")
  );

  const handleToggleEnabled = (value: boolean) => {
    setIsEnabled(value);
    SettingsManager.setSetting("enabled", value);
  };

  const handleToggleAutoSubmit = (value: boolean) => {
    setAutoSubmit(value);
    SettingsManager.setSetting("autoSubmit", value);
  };

  const handleTestSTT = () => {
    setShowOverlay(true);
  };

  return (
    <PanelSection title="STT Keyboard Settings">
      <PanelSectionRow>
        <ToggleField
          label="Enable Speech-to-Text"
          description="Enable or disable the STT keyboard feature"
          checked={isEnabled}
          onChange={handleToggleEnabled}
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <ToggleField
          label="Auto-submit"
          description="Automatically submit text after speech recognition completes"
          checked={autoSubmit}
          onChange={handleToggleAutoSubmit}
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={handleTestSTT}
          label="Test Speech-to-Text"
        />
      </PanelSectionRow>

      <PanelSectionRow>
        <div style={{ fontSize: "0.9em", opacity: 0.7 }}>
          Hotkey: Steam + Y to activate STT
        </div>
      </PanelSectionRow>

      {showOverlay && (
        <KeyboardOverlay
          onClose={() => setShowOverlay(false)}
          autoSubmit={autoSubmit}
          language={language}
        />
      )}
    </PanelSection>
  );
};

console.log("=" + "=".repeat(78) + "=");
console.log("STT KEYBOARD PLUGIN: FILE LOADED/EVALUATED - READY TO DEFINE");
console.log("=" + "=".repeat(78) + "=");

export default definePlugin((serverApi: ServerAPI) => {
  console.log("=" + "=".repeat(78) + "=");
  console.log("STT KEYBOARD PLUGIN: definePlugin() CALLBACK STARTED");
  console.log("=" + "=".repeat(78) + "=");
  const sttService = new SpeechToTextService();
  const inputManager = new InputManager();
  let overlayVisible = false;

  // Function to show the STT overlay
  const showSTTOverlay = () => {
    if (!SettingsManager.getSetting("enabled", true)) {
      console.log("STT is disabled in settings");
      return;
    }

    console.log("Activating STT overlay");
    overlayVisible = true;
    
    // Trigger overlay display
    // This will be handled by the Content component
    if (setOverlayCallback) {
      setOverlayCallback(true);
    }
  };

  // Register keyboard shortcut (Ctrl + Shift + S as fallback, Steam + Y on device)
  inputManager.registerShortcut("ctrl+shift+s", showSTTOverlay);
  
  // Register chord command for Steam + Y
  inputManager.registerChordCommand(["steam", "y"], showSTTOverlay);

  // Also try alternative mappings for Steam Deck
  inputManager.registerShortcut("alt+y", showSTTOverlay);

  console.log("=" + "=".repeat(78) + "=");
  console.log("STT KEYBOARD PLUGIN: INITIALIZATION COMPLETE");
  console.log("Registered shortcuts:", inputManager.getRegisteredShortcuts());
  console.log("Registered chords:", inputManager.getRegisteredChords());
  console.log("=" + "=".repeat(78) + "=");

  return {
    title: <div className={staticClasses.Title}>STT Keyboard</div>,
    content: <Content serverAPI={serverApi} />,
    icon: <FaMicrophone />,
    onDismount() {
      // Cleanup
      sttService.cleanup();
      inputManager.cleanup();
      console.log("STT Keyboard plugin dismounted");
    },
  };
});