# CLAUDE.md — AI Agent Business Project

## Project Overview

This project has two deliverables:

1. **Landing Page** — A single-page marketing site for an AI automation consultancy targeting Adelaide SMBs.
2. **Agent Service** — A multi-tenant FastAPI backend that hosts custom AI agents for multiple clients, handling WhatsApp/SMS/webhook inbound, LLM processing with tool use, CRM/calendar/accounting integration, and outbound messaging.

Both live in a monorepo. The landing page is a static site. The agent service is a containerised Python application.

**Current status**: Phases 1-6 complete. 10 tools registered. 89 tests passing. One live tenant (Test Physio Clinic) with HubSpot CRM.

---

## Repository Structure

```
agent-biz/
├── CLAUDE.md
├── landing-page/
│   └── index.html              # Single-file landing page (HTML + CSS + JS)
├── agent-service/
│   ├── README.md               # System documentation
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── alembic/                # DB migrations
│   │   ├── env.py
│   │   └── versions/
│   ├── docs/
│   │   └── client-onboarding.md  # Client onboarding guide
│   ├── app/
│   │   ├── main.py             # FastAPI app, lifespan, CORS, static files
│   │   ├── config.py           # Pydantic Settings from .env
│   │   ├── database.py         # Async SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── __init__.py     # Exports all models + enums
│   │   │   ├── tenant.py       # Tenant + CRMType/CalendarType/AccountingType enums
│   │   │   ├── conversation.py # Conversation history (JSONB messages)
│   │   │   └── usage.py        # Token usage tracking
│   │   ├── schemas/
│   │   │   ├── tenant.py       # Tenant CRUD schemas
│   │   │   └── webhook.py      # Webhook request/response schemas
│   │   ├── routers/
│   │   │   ├── webhooks.py     # WhatsApp, SMS, generic webhook endpoints
│   │   │   ├── tenants.py      # Admin tenant CRUD
│   │   │   └── health.py       # Health check
│   │   ├── agent/
│   │   │   ├── loop.py         # Core agent loop (message → LLM → tools → reply)
│   │   │   ├── tools.py        # Tool registry + 10 tool handlers
│   │   │   └── prompts.py      # System prompt builder per tenant
│   │   ├── integrations/
│   │   │   ├── anthropic.py    # Claude API client
│   │   │   ├── twilio.py       # WhatsApp + SMS send/receive
│   │   │   ├── hubspot.py      # HubSpot CRM
│   │   │   ├── google_sheets.py # Google Sheets CRM
│   │   │   ├── splose.py       # Splose practice management (allied health)
│   │   │   ├── google_calendar.py # Google Calendar (service account auth)
│   │   │   ├── calendly.py     # Calendly scheduling
│   │   │   ├── xero.py         # Xero accounting (OAuth2 + auto token refresh)
│   │   │   ├── slack.py        # Slack incoming webhooks
│   │   │   └── email.py        # Resend transactional email
│   │   ├── middleware/
│   │   │   ├── auth.py         # API key auth for admin endpoints
│   │   │   └── rate_limit.py   # In-memory sliding window rate limiter
│   │   ├── utils/
│   │   │   ├── encryption.py   # Fernet encrypt/decrypt
│   │   │   └── logging.py      # Structured logging
│   │   └── static/admin/       # Admin dashboard web UI
│   └── tests/
│       ├── conftest.py
│       ├── test_agent_loop.py
│       ├── test_webhooks.py
│       ├── test_tools.py
│       ├── test_google_calendar.py
│       ├── test_calendly.py
│       ├── test_slack.py
│       ├── test_email.py
│       └── test_xero.py
```

---

## Part 1: Landing Page

### Tech

Single HTML file. No framework, no build step. HTML + CSS + vanilla JS. Form submits to FormSubmit.co.

### Design Direction

Do NOT make this look like a generic AI/SaaS template. No purple gradients, no "Inter" font, no stock illustrations of robots.

**Aesthetic**: Industrial-clean. Dark background (near-black), warm accent colour (amber/gold), Clash Display (display) + Switzer (body) from Fontshare.

**Layout**: Hero → How It Works (3 steps) → What Is An Agent (explainer) → What It Does (6 cards) → Who It's For (industries) → Pricing (custom proposal box) → Contact Form → Footer.

### What NOT to do on the landing page
- No chatbot widget on the landing page itself
- No "AI" in the hero headline — focus on the outcome
- No fake testimonials
- No animations that delay content visibility

---

## Part 2: Agent Service (FastAPI)

### Tech Stack

- **Python 3.12+** / **FastAPI** (async throughout)
- **SQLAlchemy 2.0** (async) + **PostgreSQL** + **Alembic**
- **Anthropic SDK** for Claude (default: claude-sonnet-4-5)
- **Twilio SDK** for WhatsApp/SMS
- **httpx** for async HTTP to external APIs
- **Pydantic v2** for schemas + settings
- **Fernet** encryption for credentials at rest
- **Docker Compose** for local dev

### Core Concepts

#### Multi-Tenancy

Every tenant is a row in the `tenants` table. Single DB, row-level isolation.

Tenant record fields:
- `id` (UUID), `name`, `api_key` (auto-generated)
- `twilio_phone_number` — routes inbound WhatsApp/SMS
- `system_prompt` — LLM system prompt
- `tools_config` (JSONB) — `{"enabled": ["tool1", "tool2", ...]}`
- `crm_type` (enum: hubspot, google_sheets, splose, none) + `crm_credentials` (encrypted)
- `calendar_type` (enum: google_calendar, calendly, none) + `calendar_credentials` (encrypted)
- `accounting_type` (enum: xero, none) + `accounting_credentials` (encrypted)
- `twilio_account_sid` / `twilio_auth_token` (encrypted, optional — falls back to .env)
- `escalation_config` (JSONB) — `{"slack_webhook_url": "...", "email": "..."}`
- `max_conversations_per_month`, `is_active`, `created_at`, `updated_at`

#### The Agent Loop (`app/agent/loop.py`)

1. Receive user message → append to conversation history
2. Call Claude API with system prompt + tools + messages
3. If `stop_reason == "end_turn"` → extract text, return
4. If `stop_reason == "tool_use"` → execute tools, append results, loop back to step 2
5. Max 5 iterations, 30s overall timeout
6. On timeout/error → fallback message

#### Tool System (`app/agent/tools.py`)

10 tools, dispatching to integrations based on tenant config:

| Tool | Dispatches to |
|------|---------------|
| `echo` | — (testing) |
| `create_lead` | HubSpot / Splose / Google Sheets |
| `update_lead` | HubSpot / Splose |
| `search_contacts` | HubSpot / Splose / Google Sheets |
| `check_availability` | Google Calendar / Calendly / Splose |
| `book_appointment` | Google Calendar / Calendly (returns link) / Splose |
| `escalate_to_human` | Slack + Email (Resend) |
| `send_email` | Resend API |
| `search_invoices` | Xero |
| `check_payment_status` | Xero |

#### Webhook Endpoints

- `POST /webhooks/twilio/whatsapp` — Inbound WhatsApp (Twilio signature validated)
- `POST /webhooks/twilio/sms` — Inbound SMS (Twilio signature validated)
- `POST /webhooks/generic/{tenant_id}` — Web chat / custom (tenant API key auth)

#### Admin Endpoints

All require `X-API-Key` header matching `ADMIN_API_KEY` from `.env`.

- `GET/POST /admin/tenants` — List/create tenants
- `GET/PUT /admin/tenants/{id}` — Get/update tenant
- `GET /admin/tenants/{id}/usage` — Usage stats
- `GET /admin/tenants/{id}/conversations` — Recent conversations
- `GET /admin/dashboard` — Admin web UI

### Configuration (`app/config.py`)

```python
class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str
    admin_api_key: str
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    fernet_key: str = ""
    default_model: str = "claude-sonnet-4-5-20250929"
    max_agent_iterations: int = 5
    agent_timeout_seconds: int = 30
    resend_api_key: str = ""
    default_from_email: str = "noreply@relayai.com.au"
    log_level: str = "INFO"
```

### Security

- Fernet encryption for all tenant credentials at rest
- Twilio signature validation on all inbound webhooks
- All DB queries scoped by tenant_id
- In-memory sliding window rate limiter on webhook endpoints
- No message content logged in production
- Admin endpoints behind API key auth

### Development Workflow

```bash
docker compose up -d db          # Start Postgres
cp .env.example .env             # Fill in API keys
source .venv/bin/activate        # Python venv at agent-service/.venv
alembic upgrade head             # Run migrations
uvicorn app.main:app --reload    # Dev server at :8000
pytest                           # 89 tests
```

For WhatsApp testing: `ngrok http 8000` → set webhook URL in Twilio console.

---

## Integrations Reference

| Integration | Config | Credentials | Auth Type |
|-------------|--------|-------------|-----------|
| HubSpot | `crm_type: hubspot` | `crm_credentials` (API key string) | API key |
| Google Sheets | `crm_type: google_sheets` | `crm_credentials` (JSON: sheet_id + service account) | Service account |
| Splose | `crm_type: splose` | `crm_credentials` (JSON: api_key + default IDs) | API key |
| Google Calendar | `calendar_type: google_calendar` | `calendar_credentials` (JSON: client_email, private_key, calendar_id) | Service account |
| Calendly | `calendar_type: calendly` | `calendar_credentials` (JSON: api_key, event_type_uri) | Personal Access Token |
| Xero | `accounting_type: xero` | `accounting_credentials` (JSON: OAuth2 creds) | OAuth2 (auto-refresh) |
| Slack | `escalation_config.slack_webhook_url` | In escalation_config | Incoming Webhook |
| Email (Resend) | `escalation_config.email` | `RESEND_API_KEY` in .env | API key |
| WhatsApp | `twilio_phone_number` | `twilio_account_sid` + `twilio_auth_token` | API key |
| SMS | `twilio_phone_number` | `twilio_account_sid` + `twilio_auth_token` | API key |

---

## Splose Integration Details

Splose is a practice management platform for allied health and NDIS providers. API docs: https://docs.splose.com/introduction

### API Basics
- **Base URL**: `https://api.splose.com/v1`
- **Auth**: Bearer token. API keys created in Splose dashboard.
- **Required header**: `User-Agent` must be present.
- **Rate limit**: 60 calls/min.
- **Pagination**: Cursor-based (`id_gt` / `id_lt`).

### Endpoints We Use
- `GET/POST /patients` — Search/create patients
- `GET /patients/{id}` — Get patient details
- `GET /practitioners` — List practitioners
- `GET /availabilities/{practitionerId}` — Practitioner availability (max 100 days)
- `POST /appointments` — Book appointment (requires serviceId, locationId, practitionerId, patientId)

### Key Quirks
- Patient fields are **lowercase** (`firstname`), Contact fields are **camelCase** (`firstName`)
- Availability returns `HH:mm` strings + separate `date` field
- `PUT /patients/{id}` returns `1`, not the patient object

### Tenant Config for Splose
```json
{
  "api_key": "...",
  "default_practitioner_id": 1,
  "default_service_id": 1,
  "default_location_id": 1
}
```

---

## Key Design Decisions

- **Sonnet over Opus** — fast enough for real-time chat, significantly cheaper
- **No LangChain** — agent loop is simple enough; raw Anthropic SDK avoids dependency overhead
- **JSONB for conversation history** — stores raw Anthropic message format, replays directly
- **Single service** — no microservices at 10-30 tenants scale
- **No Redis** — in-memory rate limiting, Postgres for everything else
- **Splose for allied health** — dominant tool in Australian allied health vertical
