# API Key Management

## Quick Links

| Service | Purpose | Get API Key | Free Tier |
|---------|---------|-------------|----------|
| **OpenAI** | LLM for agents (Required) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | $5 free credit |
| **Serper** | Google search for news | [serper.dev](https://serper.dev) | 2,500 queries/month |
| **Alpha Vantage** | Company fundamentals | [alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) | 25 requests/day |
| **Twelve Data** | Market data (optional) | [twelvedata.com/apikey](https://twelvedata.com/apikey) | 800 requests/day |
| **MongoDB Atlas** | Database for jobs | [mongodb.com/cloud/atlas/register](https://www.mongodb.com/cloud/atlas/register) | 512MB free cluster |

---

## How to Get API Keys

### 1. OpenAI API Key (Required)

**Step-by-step:**
1. Go to [platform.openai.com](https://platform.openai.com)
2. Sign up or log in to your account
3. Click your profile icon → **View API Keys**
4. Click **Create new secret key**
5. Name it "Finance Insight Service"
6. Copy the key (starts with `sk-proj-...`)
7. **Save it immediately** - you won't see it again!

**Pricing:**
- GPT-4o: $2.50 / 1M input tokens, $10 / 1M output tokens
- GPT-4o-mini: $0.15 / 1M input tokens, $0.60 / 1M output tokens
- Average query cost: ~$0.10-0.30 with GPT-4o

**Important:** Add billing information at [platform.openai.com/settings/billing](https://platform.openai.com/settings/billing) to increase rate limits.

### 2. Serper API Key (Recommended)

**Step-by-step:**
1. Go to [serper.dev](https://serper.dev)
2. Sign up with Google account
3. Dashboard automatically shows your API key
4. Copy the key (long alphanumeric string)

**Free Tier:**
- 2,500 queries per month
- No credit card required
- Resets monthly

**Alternative:** SerpAPI ([serpapi.com](https://serpapi.com)) - 100 queries/month free

### 3. Alpha Vantage API Key (Recommended)

**Step-by-step:**
1. Go to [alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key)
2. Enter your email and click **GET FREE API KEY**
3. Key is sent to your email instantly
4. Copy the key (alphanumeric string)

**Free Tier:**
- 25 API requests per day
- 5 requests per minute
- No credit card required

**Use Case:** Fetches P/E ratio, EPS, revenue, profit margins for fundamental analysis.

### 4. Twelve Data API Key (Optional)

**Step-by-step:**
1. Go to [twelvedata.com](https://twelvedata.com)
2. Sign up for free account
3. Go to [Dashboard → API Key](https://twelvedata.com/apikey)
4. Copy your API key

**Free Tier:**
- 800 requests per day
- Real-time and historical market data

**Note:** System falls back to **Stooq** (free) if Twelve Data key is not provided.

### 5. MongoDB Atlas Setup (Required)

**Step-by-step:**

#### A. Create Cluster
1. Go to [mongodb.com/cloud/atlas/register](https://www.mongodb.com/cloud/atlas/register)
2. Sign up with Google or email
3. Choose **Free Shared Cluster** (M0)
4. Select **AWS** provider
5. Choose **Mumbai (ap-south-1)** region for low latency
6. Name cluster: `finance-insight-cluster`
7. Click **Create Cluster** (takes 3-5 minutes)

#### B. Create Database User
1. Go to **Database Access** (left sidebar)
2. Click **Add New Database User**
3. Choose **Password** authentication
4. Username: `financeapp`
5. Password: Click **Autogenerate Secure Password** (save this!)
6. Database User Privileges: **Read and write to any database**
7. Click **Add User**

#### C. Allow Network Access
1. Go to **Network Access** (left sidebar)
2. Click **Add IP Address**
3. Choose **Allow Access from Anywhere** (0.0.0.0/0)
   - For production, restrict to your Kubernetes cluster IPs
4. Click **Confirm**

#### D. Get Connection String
1. Go to **Database** (left sidebar)
2. Click **Connect** on your cluster
3. Choose **Connect your application**
4. Driver: **Python**, Version: **3.12 or later**
5. Copy connection string:
   ```
   mongodb+srv://financeapp:<password>@finance-insight-cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
6. Replace `<password>` with your actual password from step B
7. This is your **MONGO_URI**

#### E. Create Database and Collections
1. Click **Browse Collections**
2. Click **Add My Own Data**
3. Database name: `finance_insight`
4. Collection name: `jobs`
5. Click **Create**

**Collections needed:**
- `jobs` - Stores async job queue
- `threads` - Stores chat conversation threads
- `messages` - Stores individual chat messages
- `traces` - Stores agent execution traces

*(Backend auto-creates these on first run)*

#### F. Configure TTL Index (Auto-cleanup)
1. In Collections view, click `jobs` collection
2. Go to **Indexes** tab
3. Click **Create Index**
4. Fields: `updated_at: 1`
5. Options: `expireAfterSeconds: 3600` (1 hour)
6. Click **Review** → **Confirm**

This automatically deletes old jobs after 1 hour.

**Free Tier Limits:**
- 512 MB storage
- Shared RAM and CPU
- 100 max connections
- Sufficient for development and small-scale production

**Cost:** Free forever, no credit card required for M0 tier.

---

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
