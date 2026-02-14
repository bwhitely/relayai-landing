# RelayAI Agent Service

Multi-tenant AI agent backend for Australian SMBs. Handles inbound messages (WhatsApp, SMS, web), runs them through a Claude-powered agent loop with tool use, and dispatches to CRM, calendar, accounting, and notification integrations.

## Architecture

```
Inbound Message (WhatsApp / SMS / Web)
    │
    ▼
┌─────────────────────────────┐
│  Webhook Router             │  Validates signature, identifies tenant
│  (app/routers/webhooks.py)  │  by phone number or API key
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  Agent Loop                 │  System prompt + conversation history
│  (app/agent/loop.py)        │  → Claude API → tool execution → reply
│                             │  Max 5 iterations, 30s timeout
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  Tool Registry              │  10 tools dispatching to integrations
│  (app/agent/tools.py)       │  based on tenant config (crm_type,
│                             │  calendar_type, accounting_type)
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│  Integrations                                       │
│  HubSpot │ Splose │ Google Sheets │ Google Calendar  │
│  Calendly │ Xero │ Slack │ Resend (Email) │ Twilio  │
└─────────────────────────────────────────────────────┘
```

## Tech Stack

- **Python 3.12+** / **FastAPI** (async throughout)
- **SQLAlchemy 2.0** (async) + **PostgreSQL** + **Alembic** migrations
- **Anthropic SDK** for Claude API (default model: claude-sonnet-4-5)
- **Twilio SDK** for WhatsApp/SMS
- **httpx** for async HTTP to CRM/calendar/accounting APIs
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
- **Agent behaviour**: system prompt, tools_config (which tools are enabled)
- **CRM**: `crm_type` (hubspot / google_sheets / splose / none) + encrypted `crm_credentials`
- **Calendar**: `calendar_type` (google_calendar / calendly / none) + encrypted `calendar_credentials`
- **Accounting**: `accounting_type` (xero / none) + encrypted `accounting_credentials`
- **Escalation**: `escalation_config` JSON (slack_webhook_url, email)
- **Limits**: max_conversations_per_month, is_active

## Agent Loop

The core loop in `app/agent/loop.py`:

1. Receive user message
2. Load tenant config + conversation history
3. Build system prompt + enabled tools
4. Call Claude API with messages + tools
5. If `stop_reason == "end_turn"` → extract text response, done
6. If `stop_reason == "tool_use"` → execute each tool, append results, go to step 4
7. Cap at 5 iterations (configurable) with 30s overall timeout

Conversation history is stored as raw Anthropic message format (JSONB) so it replays directly without transformation.

## Tools (10 total)

| Tool | Purpose | Dispatches to |
|------|---------|---------------|
| `echo` | Testing | — |
| `create_lead` | Save customer contact | HubSpot / Splose / Google Sheets |
| `update_lead` | Update existing contact | HubSpot / Splose |
| `search_contacts` | Find existing customer | HubSpot / Splose / Google Sheets |
| `check_availability` | Query open slots | Google Calendar / Calendly / Splose |
| `book_appointment` | Book a time slot | Google Calendar / Calendly (link) / Splose |
| `escalate_to_human` | Notify business owner | Slack + Email (Resend) |
| `send_email` | Email a customer | Resend API |
| `search_invoices` | Search invoices | Xero |
| `check_payment_status` | Invoice payment details | Xero |

Tools dispatch to different integrations based on tenant config (e.g. `crm_type=hubspot` routes `create_lead` to HubSpot, `crm_type=splose` routes it to Splose).

## API Endpoints

### Webhooks (inbound messages)

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /webhooks/twilio/whatsapp` | Twilio signature | Inbound WhatsApp messages |
| `POST /webhooks/twilio/sms` | Twilio signature | Inbound SMS messages |
| `POST /webhooks/generic/{tenant_id}` | `X-API-Key` (tenant) | Web chat / custom integrations |

### Admin (tenant management)

All admin endpoints require `X-API-Key` header matching `ADMIN_API_KEY` from `.env`.

| Endpoint | Purpose |
|----------|---------|
| `GET /admin/tenants` | List all tenants |
| `POST /admin/tenants` | Create a tenant |
| `GET /admin/tenants/{id}` | Get tenant details |
| `PUT /admin/tenants/{id}` | Update tenant config |
| `GET /admin/tenants/{id}/usage` | Usage stats (tokens, cost) |
| `GET /admin/tenants/{id}/conversations` | Recent conversations |
| `GET /admin/dashboard` | Admin web UI |

### Other

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Health check |

## Project Structure

```
app/
├── main.py                    # FastAPI app, lifespan, CORS, static files
├── config.py                  # Pydantic Settings from .env
├── database.py                # Async SQLAlchemy engine + session
├── agent/
│   ├── loop.py                # Core agent loop (message → LLM → tools → reply)
│   ├── tools.py               # Tool registry, dispatch, 10 tool handlers
│   └── prompts.py             # System prompt builder per tenant
├── models/
│   ├── tenant.py              # Tenant model + CRMType/CalendarType/AccountingType enums
│   ├── conversation.py        # Conversation history (JSONB messages)
│   └── usage.py               # Token usage tracking
├── schemas/
│   ├── tenant.py              # Pydantic schemas for tenant CRUD
│   └── webhook.py             # Webhook request/response schemas
├── routers/
│   ├── webhooks.py            # WhatsApp, SMS, generic webhook endpoints
│   ├── tenants.py             # Admin tenant CRUD
│   └── health.py              # Health check
├── integrations/
│   ├── anthropic.py           # Claude API client
│   ├── twilio.py              # WhatsApp + SMS send/receive
│   ├── hubspot.py             # HubSpot CRM
│   ├── google_sheets.py       # Google Sheets CRM
│   ├── splose.py              # Splose practice management
│   ├── google_calendar.py     # Google Calendar
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
└── static/admin/              # Admin dashboard web UI
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
| `RESEND_API_KEY` | No | For email sending (escalations + send_email tool) |
| `DEFAULT_FROM_EMAIL` | No | Sender address for emails |
| `DEFAULT_MODEL` | No | Claude model (default: claude-sonnet-4-5) |
| `MAX_AGENT_ITERATIONS` | No | Tool call loop cap (default: 5) |
| `AGENT_TIMEOUT_SECONDS` | No | Overall timeout (default: 30s) |

## Security

- **Credential encryption**: All tenant secrets (CRM keys, Twilio tokens, calendar/accounting creds) encrypted with Fernet at rest
- **Twilio signature validation**: Every inbound WhatsApp/SMS request validated against Twilio's signature
- **Tenant isolation**: All DB queries scoped by tenant_id
- **Rate limiting**: In-memory sliding window on webhook endpoints
- **Admin auth**: API key header required for all admin endpoints
- **No message logging**: Only metadata (tenant_id, token counts) logged in production — message content is not logged

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_tools.py
```

89 tests covering: agent loop, tool dispatch, webhook endpoints, integrations (Twilio, HubSpot, Splose, Google Calendar, Calendly, Slack, Email, Xero), and tenant CRUD.

## Deployment

Target: Single VPS with Docker Compose + Caddy reverse proxy.

```bash
# Production
docker compose -f docker-compose.prod.yml up -d
```

- Caddy handles TLS automatically
- Systemd service for restart on reboot
- Daily Postgres backups to object storage
- UptimeRobot monitoring `/health`
