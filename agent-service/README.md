# RelayAI Agent Service

Multi-tenant AI agent backend for Australian SMBs. Handles inbound messages (WhatsApp, SMS, Facebook Messenger, Instagram DMs, web chat) and scheduled automations, runs them through a Claude-powered agent loop with tool use, and dispatches to CRM, calendar, accounting, and notification integrations.

## Architecture

```
Inbound Message (WhatsApp / SMS / Messenger / Instagram / Web)
    │                           ┌──────────────────────────┐
    │                           │  Scheduler (APScheduler) │  Cron-triggered
    │                           │  (app/agent/scheduler.py)│  automations
    │                           └────────────┬─────────────┘
    ▼                                        │
┌─────────────────────────────┐             │
│  Webhook Router             │  Validates signature, identifies tenant
│  (app/routers/webhooks.py)  │  by phone number or API key
└──────────┬──────────────────┘             │
           │                                │
           └──────────────┬─────────────────┘
                          ▼
┌─────────────────────────────┐
│  Agent Loop                 │  System prompt + conversation history
│  (app/agent/loop.py)        │  → Claude API → tool execution → reply
│                             │  Max 5 iterations, 30s timeout
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  Tool Registry              │  14 tools dispatching to integrations
│  (app/agent/tools.py)       │  based on tenant config
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│  Integrations                                               │
│  HubSpot │ Splose │ Google Sheets │ Google Calendar         │
│  Calendly │ Xero │ Slack │ Resend (Email) │ Twilio │ httpx  │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Python 3.12+** / **FastAPI** (async throughout)
- **SQLAlchemy 2.0** (async) + **PostgreSQL** + **Alembic** migrations
- **Anthropic SDK** for Claude API (default model: claude-sonnet-4-5)
- **Twilio SDK** for WhatsApp/SMS
- **APScheduler 3.x** for scheduled per-tenant cron automations
- **httpx** for async HTTP to external APIs
- **Pydantic v2** for schemas + settings
- **Fernet** encryption for tenant credentials at rest
- **Docker Compose** for local dev

## Quick Start

```bash
# 1. Start Postgres
docker compose up -d db

# 2. Set up environment
cp .env.example .env
# Fill in your API keys (Anthropic, Twilio, Resend, Fernet key)

# 3. Create venv and install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 4. Run migrations
alembic upgrade head

# 5. Start the server
uvicorn app.main:app --reload

# 6. Run tests
pytest
```

The server runs at `http://localhost:8000`. Health check: `GET /health`.

## Multi-Tenancy

Every client business is a row in the `tenants` table. All queries are scoped by `tenant_id` — single database, row-level isolation.

A tenant record defines:
- **Identity**: name, Twilio phone number, API key
- **Agent behaviour**: system prompt, tools_config (which tools are enabled + any custom HTTP endpoints)
- **CRM**: `crm_type` (hubspot / google_sheets / splose / none) + encrypted `crm_credentials`
- **Calendar**: `calendar_type` (google_calendar / calendly / none) + encrypted `calendar_credentials`
- **Accounting**: `accounting_type` (xero / none) + encrypted `accounting_credentials`
- **Channels**: `twilio_phone_number`, `meta_page_id` + `meta_credentials`
- **Escalation**: `escalation_config` JSON (slack_webhook_url, email)
- **Limits**: max_conversations_per_month, is_active

## Agent Loop

The core loop in `app/agent/loop.py`:

1. Receive user message (or scheduled job prompt)
2. Load tenant config + conversation history
3. Build system prompt + enabled tools
4. Call Claude API with messages + tools
5. If `stop_reason == "end_turn"` → extract text response, done
6. If `stop_reason == "tool_use"` → execute each tool, append results, go to step 4
7. Cap at 5 iterations (configurable) with 30s overall timeout

Conversation history is stored as raw Anthropic message format (JSONB) so it replays directly without transformation. Scheduled job runs use a fresh one-shot context (no persistent history).

## Tools (14 total)

| Tool | Purpose | Dispatches to |
|------|---------|---------------|
| `echo` | Testing | — |
| `create_lead` | Save customer contact | HubSpot / Splose / Google Sheets |
| `update_lead` | Update existing contact | HubSpot / Splose |
| `search_contacts` | Find existing customer | HubSpot / Splose / Google Sheets |
| `check_availability` | Query open slots | Google Calendar / Calendly / Splose |
| `book_appointment` | Book a time slot | Google Calendar / Calendly (link) / Splose |
| `list_appointments` | List upcoming bookings | Google Calendar / Calendly / Splose |
| `cancel_appointment` | Cancel a booking | Google Calendar / Calendly / Splose |
| `escalate_to_human` | Notify business owner | Slack + Email (Resend) |
| `send_email` | Email a customer | Resend API |
| `search_invoices` | Search invoices | Xero |
| `check_payment_status` | Invoice payment details | Xero |
| `process_document` | Extract data from PDF/image | Claude vision (multimodal) |
| `call_http` | Call pre-configured API endpoint | Any HTTP API (tenant-configured) |

Tools dispatch based on tenant config (e.g. `crm_type=hubspot` routes `create_lead` to HubSpot). The `call_http` tool uses endpoints pre-configured in `tools_config.http_endpoints` — no arbitrary URLs are permitted.

## Scheduled Automations

Each tenant can have multiple scheduled jobs (`scheduled_jobs` table). Each job defines:

- `cron_expression` — standard 5-field cron (UTC), e.g. `"0 9 * * 1"` = Mon 9am
- `prompt` — the instruction sent to the agent (e.g. "Summarise this week's bookings and email it to the owner")
- `delivery_channel` — `email` or `slack` or `none`
- `delivery_target` — email address or Slack webhook URL

The scheduler starts automatically on app startup (APScheduler `AsyncIOScheduler`). Admin CRUD operations update the live scheduler without a restart.

## API Endpoints

### Webhooks (inbound messages)

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /webhooks/twilio/whatsapp` | Twilio signature | Inbound WhatsApp |
| `POST /webhooks/twilio/sms` | Twilio signature | Inbound SMS |
| `POST /webhooks/meta` | Meta signature + verify token | Facebook Messenger + Instagram DMs |
| `POST /webhooks/generic/{tenant_id}` | `X-API-Key` (tenant) | Web chat / custom |

### Admin (tenant management)

All admin endpoints require `X-API-Key: ADMIN_API_KEY`.

| Endpoint | Purpose |
|----------|---------|
| `GET /admin/tenants` | List all tenants |
| `POST /admin/tenants` | Create a tenant |
| `GET /admin/tenants/{id}` | Get tenant details |
| `PUT /admin/tenants/{id}` | Update tenant config |
| `GET /admin/tenants/{id}/usage` | Usage stats |
| `GET /admin/tenants/{id}/conversations` | Recent conversations |
| `GET /admin/tenants/{id}/webhook-errors` | Recent webhook errors |
| `GET /admin/tenants/{id}/scheduled-jobs` | List scheduled jobs |
| `POST /admin/tenants/{id}/scheduled-jobs` | Create scheduled job |
| `GET /admin/tenants/{id}/scheduled-jobs/{job_id}` | Get job |
| `PUT /admin/tenants/{id}/scheduled-jobs/{job_id}` | Update job |
| `DELETE /admin/tenants/{id}/scheduled-jobs/{job_id}` | Delete job |
| `POST /admin/tenants/{id}/scheduled-jobs/{job_id}/run` | Trigger immediate run |
| `GET /admin/dashboard` | Admin web UI |

### Client dashboard

Authenticated via the tenant's own API key (not the admin key).

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /client/me` | `X-API-Key` (tenant) | Tenant name + limit |
| `GET /client/stats` | `X-API-Key` (tenant) | Monthly stats, chart data |
| `GET /client/conversations` | `X-API-Key` (tenant) | Recent conversations (anonymised) |
| `GET /client/` | — | Client dashboard web UI |

### Other

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Health check |

## Project Structure

```
app/
├── main.py                    # FastAPI app, lifespan, CORS, static files, scheduler start
├── config.py                  # Pydantic Settings from .env
├── database.py                # Async SQLAlchemy engine + session
├── agent/
│   ├── loop.py                # Core agent loop (message → LLM → tools → reply)
│   ├── tools.py               # Tool registry + 14 tool handlers
│   ├── scheduler.py           # APScheduler: load/run/deliver scheduled jobs
│   └── prompts.py             # System prompt builder per tenant
├── models/
│   ├── tenant.py              # Tenant model + CRMType/CalendarType/AccountingType enums
│   ├── conversation.py        # Conversation history (JSONB messages)
│   ├── scheduled_job.py       # ScheduledJob model + DeliveryChannel enum
│   ├── usage.py               # Token usage tracking
│   └── webhook_error.py       # Failed webhook log
├── schemas/
│   ├── tenant.py              # Pydantic schemas for tenant CRUD
│   └── webhook.py             # Webhook request/response schemas
├── routers/
│   ├── webhooks.py            # WhatsApp, SMS, Meta, generic webhook endpoints
│   ├── tenants.py             # Admin tenant CRUD
│   ├── scheduled_jobs.py      # Admin CRUD for scheduled automations
│   ├── client.py              # Client-facing dashboard API (tenant auth)
│   └── health.py              # Health check
├── integrations/
│   ├── anthropic.py           # Claude API client
│   ├── twilio.py              # WhatsApp + SMS send/receive
│   ├── hubspot.py             # HubSpot CRM
│   ├── google_sheets.py       # Google Sheets CRM
│   ├── splose.py              # Splose allied health practice management
│   ├── google_calendar.py     # Google Calendar (service account)
│   ├── calendly.py            # Calendly scheduling
│   ├── xero.py                # Xero accounting (OAuth2 + auto token refresh)
│   ├── slack.py               # Slack incoming webhooks
│   └── email.py               # Resend transactional email
├── middleware/
│   ├── auth.py                # API key auth for admin endpoints
│   └── rate_limit.py          # In-memory sliding window rate limiter
├── utils/
│   ├── encryption.py          # Fernet encrypt/decrypt for credentials
│   └── logging.py             # Structured logging config
└── static/
    ├── admin/                 # Admin dashboard web UI
    └── client/                # Client-facing dashboard web UI
```

## Environment Variables

See `.env.example` for all variables. Key ones:

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | Yes | Claude API key (shared across all tenants) |
| `ADMIN_API_KEY` | Yes | Auth for admin endpoints |
| `FERNET_KEY` | Yes | Encryption key for tenant credentials |
| `TWILIO_ACCOUNT_SID` | Yes | Fallback Twilio credentials |
| `TWILIO_AUTH_TOKEN` | Yes | Fallback Twilio credentials |
| `RESEND_API_KEY` | No | For email sending (escalations, send_email, scheduled jobs) |
| `DEFAULT_FROM_EMAIL` | No | Sender address for emails |
| `DEFAULT_MODEL` | No | Claude model (default: claude-sonnet-4-5) |
| `MAX_AGENT_ITERATIONS` | No | Tool call loop cap (default: 5) |
| `AGENT_TIMEOUT_SECONDS` | No | Overall timeout (default: 30s) |

## Security

- **Credential encryption**: All tenant secrets encrypted with Fernet at rest
- **Twilio signature validation**: Every inbound WhatsApp/SMS request validated
- **Meta signature validation**: Messenger/Instagram webhooks validated with app secret
- **Tenant isolation**: All DB queries scoped by tenant_id
- **Rate limiting**: In-memory sliding window on webhook endpoints
- **Admin auth**: API key header required for all admin endpoints
- **Client auth**: Tenant's own API key for client dashboard (separate from admin key)
- **No arbitrary HTTP**: `call_http` tool only reaches pre-configured endpoints
- **No message logging**: Only metadata logged in production

## Testing

```bash
pytest          # 122 tests
pytest -v       # verbose
pytest tests/test_tools.py   # specific file
```

Tests cover: agent loop, all 14 tools, webhook endpoints, integrations (Twilio, Meta, HubSpot, Splose, Google Calendar, Calendly, Slack, Email, Xero), tenant CRUD, and client dashboard.

## Deployment

Target: Single VPS with Docker Compose + Caddy reverse proxy.

```bash
docker compose -f docker-compose.prod.yml up -d
```

- Caddy handles TLS automatically
- Systemd service for restart on reboot
- Daily Postgres backups to object storage
- UptimeRobot monitoring `/health`
- Scheduler restarts automatically with the process — jobs reload from DB on startup
