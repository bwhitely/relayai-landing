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

This is where you connect external messaging platforms to your API so inbound messages reach the agent. Each platform has a different account/ownership model — read carefully.

### Twilio (WhatsApp + SMS)

**Account model:** You own one Twilio account. You buy a phone number per client within that account. All webhook traffic goes to your single API.

Optionally, a client can use their own Twilio account — set `twilio_account_sid` + `twilio_auth_token` on the tenant and it overrides the shared `.env` credentials for sending replies. But for most clients, your shared account is simpler.

**Setup per phone number:**

1. In the [Twilio Console](https://console.twilio.com), go to **Phone Numbers → Manage → Active Numbers**
2. Select (or buy) the number for this client
3. Under **Messaging > A MESSAGE COMES IN**:
   - Webhook URL: `https://api.relayai.com.au/webhooks/twilio/sms`
   - Method: HTTP POST
4. For **WhatsApp** on the same number, go to **Messaging → Try it out → Send a WhatsApp message** (sandbox) or **Senders → WhatsApp Senders** (production):
   - Webhook URL: `https://api.relayai.com.au/webhooks/twilio/whatsapp`
   - Method: HTTP POST
5. On the tenant record, set `twilio_phone_number` to the E.164 number (e.g. `+61412345678`) — this is how inbound messages are routed to the correct tenant

> **Same number, both channels:** Twilio keeps WhatsApp and SMS webhooks separate. One number can handle both — they route to different webhook URLs. Conversations are tracked separately per channel.

> **WhatsApp Business approval:** Twilio sandbox numbers work for testing. For production, you need an approved WhatsApp Business number through Twilio — this takes a few days.

### Meta (Facebook Messenger + Instagram DMs)

**Account model:** You register one Meta App (on your developer account). Each client connects their Facebook Page to your app and generates a Page Access Token. The client's page is theirs — you just process messages on their behalf.

Both Messenger and Instagram DMs use the same webhook endpoint. Meta differentiates them via the `object` field in the payload.

**One-time setup (do this once):**

1. Go to [developers.facebook.com](https://developers.facebook.com) — create a developer account if needed
2. **Create a new App:** Create App → Business → Other
3. Add the **Messenger** product (and **Instagram** if clients want IG DMs)
4. Go to **App Settings → Basic** and copy the **App Secret** — you'll need this for every tenant

**Per-client setup:**

1. In your Meta App, go to **Messenger → Settings → Access Tokens**
2. Click **Add or Remove Pages** — the client logs into Facebook and selects their Business Page
3. Click **Generate Token** for their page:
   - Copy the **Page Access Token** → this is `page_access_token`
   - Note the **Page ID** (shown next to the page name) → this is `meta_page_id`
4. Go to **Messenger → Settings → Webhooks** and click **Add Callback URL**:
   - Callback URL: `https://api.relayai.com.au/webhooks/meta`
   - Verify Token: choose any string (e.g. `relay-verify-abc123`) → this is `verify_token`
   - Click **Verify and Save** — Meta sends a GET request to confirm
   - Subscribe to the **messages** webhook field
5. For Instagram (optional): go to **Instagram → Settings**, connect the client's Instagram Professional account (must be linked to their Facebook Page), and subscribe to `messages`
6. Update the tenant:
   ```bash
   curl -X PUT https://api.relayai.com.au/admin/tenants/TENANT_ID \
     -H "X-API-Key: YOUR_ADMIN_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "meta_page_id": "123456789012345",
       "meta_credentials": "{\"app_secret\": \"your-app-secret\", \"page_access_token\": \"EAAxxxxxxx...\", \"verify_token\": \"relay-verify-abc123\"}"
     }'
   ```

> **Why one Meta App?** A single Meta App can handle multiple client pages. Each page gets its own access token. The webhook URL is shared — inbound messages include the page ID, which we use to look up the tenant. You don't need a separate Meta App per client.

> **Token expiry:** Short-lived Page Access Tokens expire after ~1 hour. Always generate a **long-lived token** (valid ~60 days) or use a **System User token** (never expires). See [Meta docs on long-lived tokens](https://developers.facebook.com/docs/pages/access-tokens).

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

---

## n8n Deployment (Workflow Automation Track)

n8n runs as a separate Railway service alongside the agent service.
Access it at: https://n8n.relayai.com.au (admin credentials in password manager — clients never access this directly).

### Railway service: `n8n`
### Database: `n8n-db` (separate Postgres — do not share with agent-db)

### Environment variables

| Variable | Notes |
|---|---|
| `N8N_BASIC_AUTH_ACTIVE` | `true` |
| `N8N_BASIC_AUTH_USER` | `admin` |
| `N8N_BASIC_AUTH_PASSWORD` | In password manager |
| `N8N_ENCRYPTION_KEY` | In password manager — see warning below |
| `WEBHOOK_URL` | `https://n8n.relayai.com.au` |
| `N8N_RUNNERS_ENABLED` | `true` |
| `DB_TYPE` | `postgresdb` |
| `DB_POSTGRESDB_HOST` | Internal hostname from n8n-db Railway service |
| `DB_POSTGRESDB_PORT` | `5432` |
| `DB_POSTGRESDB_DATABASE` | `railway` |
| `DB_POSTGRESDB_USER` | `postgres` |
| `DB_POSTGRESDB_PASSWORD` | From n8n-db Railway service variables |
| `GENERIC_TIMEZONE` | `Australia/Adelaide` |
| `N8N_DEFAULT_LOCALE` | `en` |

### Client isolation

n8n Projects is an enterprise-only feature on self-hosted instances. Client workflows are organised using **tags and naming conventions** instead. See `n8n-templates/README.md` for the full convention.

### ⚠️ Critical: N8N_ENCRYPTION_KEY

n8n uses this key to encrypt all stored credentials (OAuth tokens, API keys, passwords).
If you lose or rotate it without a migration plan, all stored credentials across all client workflows become unrecoverable — you will need to manually reconnect every integration for every client.

- Store it in a password manager immediately after generation
- Never auto-rotate it
- If it ever needs to change, export all credentials first and plan a migration window

Generate with: `python3 -c "import secrets; print(secrets.token_hex(32))"`

### Upgrading n8n

Railway deploys `n8nio/n8n:latest` by default. For production stability, pin to a specific version:

1. In the n8n Railway service → Settings → Source → change image to `n8nio/n8n:1.x.x`
2. Always check the [n8n changelog](https://github.com/n8n-io/n8n/releases) before upgrading — breaking changes occur between minor versions
3. Test with a canary workflow before upgrading if clients have active workflows

### Setting up the domain

1. In the n8n Railway service → Settings → Networking → Custom Domain
2. Add `n8n.relayai.com.au`
3. Add the CNAME record your DNS provider pointing to the Railway-generated hostname
4. SSL provisions automatically (usually < 5 minutes)
