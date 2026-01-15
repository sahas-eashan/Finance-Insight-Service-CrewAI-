"use client";

import { useRef, useState, type ChangeEvent } from "react";
import Icon from "./Icon";

type ChatComposerProps = {
  onSend: (message: string) => void;
  disabled?: boolean;
};

export default function ChatComposer({ onSend, disabled }: ChatComposerProps) {
  const [value, setValue] = useState("");
  const [showTools, setShowTools] = useState(false);
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [listening, setListening] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const submit = () => {
    if (disabled) {
      return;
    }
    const trimmed = value.trim();
    if (!trimmed && selectedTools.length === 0) {
      return;
    }
    
    // Combine tools with message if any
    let finalMessage = trimmed;
    if (selectedTools.length > 0) {
      const toolsPrefix = selectedTools.map(t => `[${t}]`).join(" ");
      finalMessage = trimmed ? `${toolsPrefix} ${trimmed}` : toolsPrefix;
    }

    onSend(finalMessage);
    setValue("");
    setSelectedTools([]);
    setIsFocused(false);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const handleAttach = () => {
    fileInputRef.current?.click();
  };

  const handleFiles = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    if (files.length) {
      setAttachments((prev) => [...prev, ...files]);
    }
    event.target.value = "";
  };

  const handleRemoveAttachment = (name: string) => {
    setAttachments((prev) => prev.filter((file) => file.name !== name));
  };

  const toolOptions = [
    "Summarize",
    "Extract action items",
    "Translate",
    "Code review",
  ];

  return (
    <div className="composer">
      <form
        className={`composer-card ${isFocused ? "is-expanded" : ""}`}
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        {attachments.length ? (
          <div className="composer-attachments">
            {attachments.map((file) => (
              <span className="attachment-chip" key={file.name}>
                {file.name}
                <button
                  className="attachment-remove"
                  type="button"
                  onClick={() => handleRemoveAttachment(file.name)}
                  aria-label={`Remove ${file.name}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}
        <textarea
          className="composer-input"
          placeholder="Type your message"
          rows={1}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={(e) => {
            // Only collapse if we're not clicking into something else inside the composer
            if (!e.currentTarget.parentElement?.contains(e.relatedTarget as Node)) {
              setIsFocused(false);
            }
          }}
          disabled={disabled}
          aria-label="Message input"
        />
        {listening || voiceMode ? (
          <div className="composer-status">
            {listening ? "Listening…" : null}
            {listening && voiceMode ? " · " : null}
            {voiceMode ? "Voice mode enabled" : null}
          </div>
        ) : null}
        <div className="composer-row">
          <div className="composer-left">
            <button
              className="icon-circle"
              type="button"
              aria-label="Add"
              onClick={handleAttach}
            >
              <Icon name="plus" />
            </button>
            <div className="tools-wrapper">
              <button
                className="tools-button"
                type="button"
                onClick={() => setShowTools((prev) => !prev)}
                aria-expanded={showTools}
              >
                <Icon className="icon-small" name="sliders" />
                Tools
                <Icon className="icon-small" name={showTools ? "chevron-down" : "chevron-up"} />
              </button>
              {showTools ? (
                <div className="tools-menu" role="menu">
                  {toolOptions.map((tool) => (
                    <button
                      className="tools-item"
                      key={tool}
                      type="button"
                      onClick={() => {
                        if (!selectedTools.includes(tool)) {
                          setSelectedTools((prev) => [...prev, tool]);
                        }
                        setShowTools(false);
                      }}
                      role="menuitem"
                    >
                      {tool}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            {selectedTools.length > 0 && (
              <div className="composer-selected-tools">
                {selectedTools.map((tool) => (
                  <span className="tool-chip" key={tool}>
                    {tool}
                    <button
                      className="tool-chip-remove"
                      type="button"
                      onClick={() =>
                        setSelectedTools((prev) =>
                          prev.filter((t) => t !== tool),
                        )
                      }
                      aria-label={`Remove ${tool}`}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="composer-right">
            <button
              className="icon-circle"
              type="button"
              aria-label="Microphone"
              aria-pressed={listening}
              onClick={() => setListening((prev) => !prev)}
            >
              <Icon name="mic" />
            </button>
            <button
              className="icon-circle"
              type="button"
              aria-label="Audio"
              aria-pressed={voiceMode}
              onClick={() => setVoiceMode((prev) => !prev)}
            >
              <Icon name="wave" />
            </button>
          </div>
        </div>
        <div className="composer-hint">Press Enter to send, Shift + Enter for a new line.</div>
        <input
          ref={fileInputRef}
          className="composer-file-input"
          type="file"
          multiple
          onChange={handleFiles}
          hidden
        />
      </form>
    </div>
  );
}
