"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  DEFAULT_API_BASE_URL,
  getApiConfig,
  setApiConfig,
  testConnection,
  fetchConfig,
  type ServiceCapabilities,
} from "@/lib/api";

type Status = "idle" | "saving" | "saved" | "testing" | "connected" | "error";

type ApiKeys = {
  openai: string;
  serper: string;
  serpapi: string;
  twelveData: string;
  alphaVantage: string;
};

export default function SettingsForm() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [apiKey, setApiKey] = useState("");
  const [keys, setKeys] = useState<ApiKeys>({
    openai: "",
    serper: "",
    serpapi: "",
    twelveData: "",
    alphaVantage: "",
  });
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");
  const [capabilities, setCapabilities] = useState<ServiceCapabilities | null>(null);

  useEffect(() => {
    const config = getApiConfig();
    setBaseUrl(config.baseUrl);
    setApiKey(config.apiKey ?? "");
    
    // Load keys from localStorage
    const savedKeys = localStorage.getItem("financeApiKeys");
    if (savedKeys) {
      try {
        setKeys(JSON.parse(savedKeys));
      } catch (e) {
        console.error("Failed to load API keys", e);
      }
    }

    // Fetch backend capabilities
    fetchConfig().then(setCapabilities);
  }, []);

  const handleSave = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus("saving");

    const trimmedBase = baseUrl.trim() || DEFAULT_API_BASE_URL;
    const trimmedKey = apiKey.trim();

    setApiConfig({ baseUrl: trimmedBase, apiKey: trimmedKey });
    localStorage.setItem("financeApiKeys", JSON.stringify(keys));
    
    setStatus("saved");
    setMessage("Settings and API keys saved locally. Restart backend to use new keys.");
  };

  const handleTest = async () => {
    setStatus("testing");
    setMessage("Testing connection...");
    const ok = await testConnection({
      baseUrl: baseUrl.trim() || DEFAULT_API_BASE_URL,
      apiKey: apiKey.trim(),
    });
    
    if (ok) {
      const config = await fetchConfig();
      setCapabilities(config);
      setStatus("connected");
      setMessage("Backend connection successful.");
    } else {
      setStatus("error");
      setMessage("Could not reach backend.");
    }
  };

  const handleExport = () => {
    const envContent = `# Finance Insight Service API Keys
OPENAI_API_KEY=${keys.openai}
SERPER_API_KEY=${keys.serper}
SERPAPI_API_KEY=${keys.serpapi}
TWELVE_DATA_API_KEY=${keys.twelveData}
ALPHAVANTAGE_API_KEY=${keys.alphaVantage}
MONGO_URI=mongodb://localhost:27017
MONGO_DB=finance_insight
`;
    
    const blob = new Blob([envContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '.env';
    a.click();
    URL.revokeObjectURL(url);
    setMessage("Downloaded .env file. Copy to project root and restart backend.");
  };

  return (
    <form className="settings-card" onSubmit={handleSave}>
      <div className="settings-header">
        <div>
          <h1>API Configuration</h1>
          <p>Connect the UI to your Finance Insight backend and configure API keys.</p>
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
          <span>Backend API Key (optional)</span>
          <input
            className="settings-input"
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder="Optional authentication key"
          />
        </label>

        <hr style={{ border: 'none', borderTop: '1px solid var(--composer-border)', margin: '20px 0' }} />
        
        <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px' }}>AI Service API Keys</h3>

        <label className="settings-field">
          <span>OpenAI API Key <span style={{ color: 'var(--accent)' }}>*</span></span>
          <input
            className="settings-input"
            type="password"
            value={keys.openai}
            onChange={(e) => setKeys({ ...keys, openai: e.target.value })}
            placeholder="sk-..."
          />
          <small style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Required for AI agents</small>
        </label>

        <label className="settings-field">
          <span>Serper API Key</span>
          <input
            className="settings-input"
            type="password"
            value={keys.serper}
            onChange={(e) => setKeys({ ...keys, serper: e.target.value })}
            placeholder="Get from serper.dev"
          />
          <small style={{ fontSize: '11px', color: 'var(--text-muted)' }}>For news search (alternative to SerpAPI)</small>
        </label>

        <label className="settings-field">
          <span>SerpAPI Key</span>
          <input
            className="settings-input"
            type="password"
            value={keys.serpapi}
            onChange={(e) => setKeys({ ...keys, serpapi: e.target.value })}
            placeholder="Get from serpapi.com"
          />
          <small style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Alternative news search provider</small>
        </label>

        <label className="settings-field">
          <span>Twelve Data API Key</span>
          <input
            className="settings-input"
            type="password"
            value={keys.twelveData}
            onChange={(e) => setKeys({ ...keys, twelveData: e.target.value })}
            placeholder="Get from twelvedata.com"
          />
          <small style={{ fontSize: '11px', color: 'var(--text-muted)' }}>For market data (falls back to Stooq if missing)</small>
        </label>

        <label className="settings-field">
          <span>Alpha Vantage API Key</span>
          <input
            className="settings-input"
            type="password"
            value={keys.alphaVantage}
            onChange={(e) => setKeys({ ...keys, alphaVantage: e.target.value })}
            placeholder="Get from alphavantage.co"
          />
          <small style={{ fontSize: '11px', color: 'var(--text-muted)' }}>For company fundamentals and financial ratios</small>
        </label>

        {capabilities && (
          <>
            <hr style={{ border: 'none', borderTop: '1px solid var(--composer-border)', margin: '20px 0' }} />
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px' }}>Backend Service Status</h3>
            <div style={{ display: 'grid', gap: '8px', fontSize: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: capabilities.services.openai ? '#22c55e' : '#ef4444' }}>
                  {capabilities.services.openai ? '✓' : '✗'}
                </span>
                <span>OpenAI API {capabilities.services.openai ? '(configured)' : '(missing)'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: capabilities.capabilities.news_search ? '#22c55e' : '#ef4444' }}>
                  {capabilities.capabilities.news_search ? '✓' : '✗'}
                </span>
                <span>News Search {capabilities.services.serper ? '(Serper)' : capabilities.services.serpapi ? '(SerpAPI)' : '(none)'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: capabilities.services.twelveData ? '#22c55e' : '#fbbf24' }}>
                  {capabilities.services.twelveData ? '✓' : '○'}
                </span>
                <span>Market Data {capabilities.services.twelveData ? '(Twelve Data)' : '(Stooq fallback)'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: capabilities.services.alphaVantage ? '#22c55e' : '#ef4444' }}>
                  {capabilities.services.alphaVantage ? '✓' : '✗'}
                </span>
                <span>Fundamentals {capabilities.services.alphaVantage ? '(Alpha Vantage)' : '(missing)'}</span>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="settings-actions">
        <button className="button-primary" type="submit">
          Save settings
        </button>
        <button className="button-secondary" onClick={handleTest} type="button">
          Test connection
        </button>
        <button className="button-secondary" onClick={handleExport} type="button">
          Export .env file
        </button>
        {message ? (
          <span className={`settings-status settings-status--${status}`}>
            {message}
          </span>
        ) : null}
      </div>

      <div className="settings-hint">
        <strong>Note:</strong> Keys are stored locally in your browser. Click "Export .env file" 
        to download a .env file, then copy it to your project root and restart the backend.
      </div>
    </form>
  );
}
