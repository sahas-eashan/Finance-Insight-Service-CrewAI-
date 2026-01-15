"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  DEFAULT_API_BASE_URL,
  getApiConfig,
  setApiConfig,
  testConnection,
} from "@/lib/api";

type Status = "idle" | "saving" | "saved" | "testing" | "connected" | "error";

export default function SettingsForm() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const config = getApiConfig();
    setBaseUrl(config.baseUrl);
    setApiKey(config.apiKey ?? "");
  }, []);

  const handleSave = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus("saving");

    const trimmedBase = baseUrl.trim() || DEFAULT_API_BASE_URL;
    const trimmedKey = apiKey.trim();

    setApiConfig({ baseUrl: trimmedBase, apiKey: trimmedKey });
    setStatus("saved");
    setMessage("Settings saved locally.");
  };

  const handleTest = async () => {
    setStatus("testing");
    setMessage("Testing connection...");
    const ok = await testConnection({
      baseUrl: baseUrl.trim() || DEFAULT_API_BASE_URL,
      apiKey: apiKey.trim(),
    });
    setStatus(ok ? "connected" : "error");
    setMessage(
      ok ? "Backend connection successful." : "Could not reach backend.",
    );
  };

  return (
    <form className="settings-card" onSubmit={handleSave}>
      <div className="settings-header">
        <div>
          <h1>API Authentication</h1>
          <p>Connect the UI to your Flask + MongoDB agent backend.</p>
        </div>
      </div>

      <div className="settings-fields">
        <label className="settings-field">
          <span>Backend URL</span>
          <input
            className="settings-input"
            type="url"
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            placeholder="http://localhost:5000"
          />
        </label>

        <label className="settings-field">
          <span>API Key</span>
          <input
            className="settings-input"
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder="Paste your API key"
          />
        </label>
      </div>

      <div className="settings-actions">
        <button className="button-primary" type="submit">
          Save settings
        </button>
        <button className="button-secondary" onClick={handleTest} type="button">
          Test connection
        </button>
        {message ? (
          <span className={`settings-status settings-status--${status}`}>
            {message}
          </span>
        ) : null}
      </div>

      <div className="settings-hint">
        Expected endpoints: <code>GET /health</code>, <code>GET /history</code>,
        and <code>POST /chat</code>. The API key is sent as both
        <code>Authorization</code> and <code>X-API-Key</code>.
      </div>
    </form>
  );
}
