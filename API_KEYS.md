# API Key Management

## How It Works

### Development Mode
In development, the backend reads API keys from a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env

# Edit with your keys
nano .env
```

The backend must be **restarted** after changing `.env`:
```bash
uv run finance_insight_api --host 0.0.0.0 --port 5000
```

### Production Mode
For production deployments, set environment variables directly:

**Docker:**
```bash
docker run -e OPENAI_API_KEY=sk-... -e SERPER_API_KEY=... finance-insight
```

**Systemd Service:**
```ini
[Service]
Environment="OPENAI_API_KEY=sk-..."
Environment="SERPER_API_KEY=..."
```

**Cloud Platforms:**
- AWS: Use Parameter Store or Secrets Manager
- Heroku: Set Config Vars in dashboard
- Render/Railway: Use environment variables in UI

## Required vs Optional Keys

### Required
- **OPENAI_API_KEY** - AI agents won't work without this

### Recommended
- **SERPER_API_KEY** or **SERPAPI_API_KEY** - For news search
- **ALPHAVANTAGE_API_KEY** - For company fundamentals

### Optional
- **TWELVE_DATA_API_KEY** - Market data (falls back to Stooq)

## Frontend Settings Page

The settings page lets you:
1. **Enter API keys** - Stored in browser localStorage (not sent to backend)
2. **Export .env file** - Download configured .env for backend
3. **Check service status** - See which APIs are configured on backend

**Note:** Keys entered in the UI are saved locally for reference only. You must export the .env file and restart the backend for them to take effect.

## Graceful Degradation

The system adapts based on available keys:
- Missing Twelve Data → Falls back to Stooq (free, limited)
- Missing news API → Agents skip news search tasks
- Missing Alpha Vantage → Fundamentals tasks fail gracefully
- Missing OpenAI → System cannot run (required)

Check `/config` endpoint to see active capabilities:
```bash
curl http://localhost:5000/config
```
