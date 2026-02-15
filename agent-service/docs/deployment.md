# Production Deployment Guide

Deploy the RelayAI Agent Service to Railway (backend) with a Railway-managed Postgres database.

---

## Prerequisites

- [Railway account](https://railway.app) (Hobby plan, $5/month — gives you $5 credit that covers small workloads)
- GitHub repo with the `agent-service/` directory pushed
- API keys ready: Anthropic, Twilio, Resend, Fernet key
- Domain (optional but recommended): e.g. `api.relayai.com.au`

---

## Step 1: Generate secrets locally

Before touching Railway, generate the values you'll need.

```bash
# Generate a Fernet encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate an admin API key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save both — you'll paste them into Railway in Step 3.

---

## Step 2: Create the Railway project

1. Go to [railway.app/new](https://railway.app/new)
2. Click **"Deploy from GitHub Repo"** and connect your repo
3. Railway will detect the Dockerfile — set the **root directory** to `agent-service`
4. Don't deploy yet — we need the database first

### Add Postgres

1. In the same Railway project, click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway provisions a Postgres instance and gives you a connection URL
3. Copy the **internal** connection URL (format: `postgresql://user:pass@host:port/dbname`)
4. You need the **asyncpg** version — replace `postgresql://` with `postgresql+asyncpg://`:
   ```
   postgresql+asyncpg://postgres:xxxx@postgres.railway.internal:5432/railway
   ```

---

## Step 3: Set environment variables

In your Railway service (the app, not the database), go to **Variables** and add:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:xxxx@postgres.railway.internal:5432/railway` | From Step 2, with `+asyncpg` |
| `ANTHROPIC_API_KEY` | `sk-ant-xxxxx` | From [console.anthropic.com](https://console.anthropic.com) |
| `ADMIN_API_KEY` | (generated in Step 1) | Used for all admin API calls |
| `FERNET_KEY` | (generated in Step 1) | Encrypts tenant credentials at rest |
| `TWILIO_ACCOUNT_SID` | `ACxxxxx` | From [twilio.com/console](https://www.twilio.com/console) |
| `TWILIO_AUTH_TOKEN` | `xxxxx` | From Twilio console |
| `RESEND_API_KEY` | `re_xxxxx` | From [resend.com/api-keys](https://resend.com/api-keys) |
| `DEFAULT_FROM_EMAIL` | `noreply@relayai.com.au` | Must match a verified domain in Resend |
| `CORS_ORIGINS` | `https://www.relayai.com.au,https://relayai.com.au` | Comma-separated allowed origins |
| `DEFAULT_MODEL` | `claude-sonnet-4-5-20250929` | Or whichever Claude model you want |
| `MAX_AGENT_ITERATIONS` | `5` | Max tool-use loops per message |
| `AGENT_TIMEOUT_SECONDS` | `30` | Overall timeout per message |
| `LOG_LEVEL` | `INFO` | Use `WARNING` to reduce noise once stable |

---

## Step 4: Fix the Dockerfile for production

The current Dockerfile works but has a few issues for production. Update it:

```dockerfile
FROM python:3.12-slim

# Run as non-root user
RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

# Switch to non-root user
USER app

EXPOSE 8000

# Use multiple workers in production (2-4 for a small deployment)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

> **Why 2 workers?** Railway Hobby gives you 512MB–8GB RAM. Each uvicorn worker uses ~80-120MB. 2 workers handle concurrent requests while staying well within limits. Don't use `--reload` in production.

---

## Step 5: Run database migrations

Railway doesn't run migrations automatically. You have two options:

### Option A: One-off command via Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link to your project
railway login
railway link

# Run migrations (uses your Railway env vars automatically)
railway run alembic upgrade head
```

### Option B: Add a release command

In your Railway service settings, set **Custom Start Command** to:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

This runs migrations on every deploy before starting the server. Safe because Alembic is idempotent — re-running `upgrade head` on an already-migrated DB is a no-op.

> **Important:** The `alembic.ini` has a hardcoded `sqlalchemy.url`. For production, override it via the command line:
> ```bash
> alembic -x sqlalchemy.url=$DATABASE_URL upgrade head
> ```
> Or update `alembic/env.py` to read from the `DATABASE_URL` environment variable (recommended — see Step 5b below).

### Step 5b: Make alembic read DATABASE_URL from env

Update `alembic/env.py` to use the `DATABASE_URL` env var instead of the hardcoded value in `alembic.ini`:

Add this near the top of `alembic/env.py`, after the imports:

```python
import os

# Use DATABASE_URL from environment if available, otherwise fall back to alembic.ini
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)
```

This means migrations work locally (falls back to `alembic.ini`) and in production (reads `DATABASE_URL`).

---

## Step 6: Deploy

1. Push your changes to GitHub
2. Railway auto-deploys from your connected branch (usually `main`)
3. Watch the build logs in the Railway dashboard
4. Once deployed, Railway gives you a URL like `agent-service-production-xxxx.up.railway.app`

### Add a custom domain (recommended)

1. In Railway service settings → **Networking** → **Custom Domain**
2. Add `api.relayai.com.au` (or whatever you want)
3. Add the CNAME record Railway gives you to your DNS
4. Railway handles SSL automatically

---

## Step 7: Verify the deployment

```bash
# Set your production URL
API_URL="https://api.relayai.com.au"

# 1. Health check
curl $API_URL/health
# Should return: {"status": "ok"}

# 2. List tenants (should be empty)
curl $API_URL/admin/tenants -H "X-API-Key: YOUR_ADMIN_KEY"
# Should return: []

# 3. Create your first tenant
curl -X POST $API_URL/admin/tenants \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Business",
    "system_prompt": "You are a helpful assistant for Test Business.",
    "tools_config": {"enabled": ["echo"]},
    "max_conversations_per_month": 10
  }'

# 4. Test the agent (use the tenant ID and API key from the response above)
curl -X POST $API_URL/webhooks/generic/TENANT_ID \
  -H "X-API-Key: TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"sender_id": "test", "message": "Hello"}'
```

---

## Step 8: Configure external webhooks

### Twilio (WhatsApp + SMS)

1. In the [Twilio Console](https://console.twilio.com), go to your phone number settings
2. Set the webhook URLs:
   - **WhatsApp**: `https://api.relayai.com.au/webhooks/twilio/whatsapp` (POST)
   - **SMS**: `https://api.relayai.com.au/webhooks/twilio/sms` (POST)

### Meta (Facebook Messenger + Instagram)

1. In your [Meta App dashboard](https://developers.facebook.com), go to Messenger → Settings → Webhooks
2. Set callback URL: `https://api.relayai.com.au/webhooks/meta`
3. Set verify token: whatever you put in the tenant's `meta_credentials.verify_token`
4. Subscribe to the `messages` webhook field

### Landing page demo widget

Update the demo config in `landing-page/index.html` to point to your production URL:

```javascript
var DEMO_CONFIG = {
  tenantId: 'your-demo-tenant-id',
  apiKey: 'your-demo-tenant-api-key',
  apiUrl: 'https://api.relayai.com.au',
};
```

Update `CORS_ORIGINS` to include wherever the landing page is hosted.

---

## Step 9: Set up monitoring

### Railway logs

Railway streams logs in the dashboard. For quick checks:

```bash
railway logs
```

### Uptime monitoring (free)

Set up a free uptime monitor on [UptimeRobot](https://uptimerobot.com) or [Betterstack](https://betterstack.com):
- Monitor URL: `https://api.relayai.com.au/health`
- Check interval: 5 minutes
- Alert via email/Slack when it goes down

### Cost monitoring

- **Anthropic**: Set a monthly spend limit in [console.anthropic.com](https://console.anthropic.com) → Settings → Limits. Start with $20-50 while you have few tenants.
- **Railway**: The Hobby plan auto-alerts at $5 usage. Upgrade to Pro ($20/mo) when you need more resources or add more tenants.
- **Twilio**: Set usage triggers in the Twilio console → Billing → Usage Triggers.

---

## Cost estimate (small scale, 1-5 tenants)

| Service | Monthly cost | Notes |
|---------|-------------|-------|
| Railway (app) | ~$2-5 | Hobby plan, low traffic |
| Railway (Postgres) | ~$1-2 | Small DB, included in Hobby credit |
| Anthropic (Claude) | ~$5-30 | Depends on conversation volume |
| Twilio | ~$1-5 | $1/month per number + per-message fees |
| Resend | Free | Up to 3,000 emails/month on free tier |
| **Total** | **~$10-40/month** | |

---

## Ongoing operations

### Deploying updates

Just push to `main`. Railway auto-deploys. If you set up the release command (Step 5 Option B), migrations run automatically.

### Rolling back

Railway keeps previous deployments. In the dashboard, click on a previous deployment → **"Rollback"**.

### Database backups

Railway Postgres includes automatic daily backups on Pro plans. On Hobby, manually back up periodically:

```bash
railway run pg_dump -Fc $DATABASE_URL > backup_$(date +%Y%m%d).dump
```

### Scaling up

When you outgrow the Hobby plan:
1. Upgrade to Railway Pro ($20/mo, usage-based)
2. Increase `--workers` in the Dockerfile CMD (4-8 for moderate traffic)
3. If you need Redis-backed rate limiting or caching, add a Redis service in Railway

---

## Production checklist

Before going live with real clients:

- [ ] Health check returns 200
- [ ] Admin API responds with correct API key
- [ ] Test tenant created and agent responds
- [ ] Twilio webhooks configured and WhatsApp/SMS working
- [ ] Meta webhooks verified (if using Messenger/Instagram)
- [ ] CORS_ORIGINS set to your actual domains (not localhost)
- [ ] Anthropic spend limit set
- [ ] Uptime monitoring configured
- [ ] Custom domain + SSL working
- [ ] Fernet key backed up somewhere safe (losing it = losing access to all encrypted tenant credentials)
- [ ] Admin API key stored securely (password manager, not plaintext)
- [ ] Landing page demo config updated with production URL
- [ ] `LOG_LEVEL` set to `INFO` (not `DEBUG`)
