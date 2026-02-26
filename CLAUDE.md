# CLAUDE.md — AI Agent Business Project

## Project Overview

This project has two deliverables:

1. **Landing Page** — A single-page marketing site for an AI automation consultancy targeting Adelaide SMBs.
2. **Agent Service** — A multi-tenant FastAPI backend that hosts custom AI agents for multiple clients, handling WhatsApp/SMS/Messenger/Instagram/webhook inbound, scheduled automations, LLM processing with tool use, CRM/calendar/accounting integration, and outbound messaging.

Both live in a monorepo. The landing page is a static site. The agent service is a containerised Python application.

**Current status**: All core features complete. 14 tools registered. 122 tests passing. Client dashboard live at `/client/`. Scheduled automations running via APScheduler.

---

## Repository Structure

```
agent-biz/
├── CLAUDE.md
├── landing-page/
│   └── index.html              # Single-file landing page (HTML + CSS + JS)
├── n8n-templates/          # Reusable n8n workflow JSON exports (see n8n-templates/README.md)
├── clients/                # Per-client records — discovery notes and active workflow inventory
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
│   │   ├── main.py             # FastAPI app, lifespan, CORS, static files, scheduler start
│   │   ├── config.py           # Pydantic Settings from .env
│   │   ├── database.py         # Async SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── __init__.py     # Exports all models + enums
│   │   │   ├── tenant.py       # Tenant + CRMType/CalendarType/AccountingType enums
│   │   │   ├── conversation.py # Conversation history (JSONB messages)
│   │   │   ├── scheduled_job.py # ScheduledJob + DeliveryChannel enum
│   │   │   ├── usage.py        # Token usage tracking
│   │   │   └── webhook_error.py # Failed webhook log
│   │   ├── schemas/
│   │   │   ├── tenant.py       # Tenant CRUD schemas
│   │   │   └── webhook.py      # Webhook request/response schemas
│   │   ├── routers/
│   │   │   ├── webhooks.py     # WhatsApp, SMS, Meta, generic webhook endpoints
│   │   │   ├── tenants.py      # Admin tenant CRUD
│   │   │   ├── scheduled_jobs.py # Admin CRUD for scheduled automations
│   │   │   ├── client.py       # Client-facing dashboard API (tenant auth)
│   │   │   └── health.py       # Health check
│   │   ├── agent/
│   │   │   ├── loop.py         # Core agent loop (message → LLM → tools → reply)
│   │   │   ├── tools.py        # Tool registry + 14 tool handlers
│   │   │   ├── scheduler.py    # APScheduler: cron job loading, execution, delivery
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
│   │   └── static/
│   │       ├── admin/          # Admin dashboard web UI
│   │       └── client/         # Client-facing dashboard web UI
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
- **APScheduler 3.x** (`AsyncIOScheduler`) for per-tenant cron automations
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
- `tools_config` (JSONB) — `{"enabled": ["tool1", ...], "http_endpoints": [...]}`
- `crm_type` (enum: hubspot, google_sheets, splose, none) + `crm_credentials` (encrypted)
- `calendar_type` (enum: google_calendar, calendly, none) + `calendar_credentials` (encrypted)
- `accounting_type` (enum: xero, none) + `accounting_credentials` (encrypted)
- `meta_page_id` + `meta_credentials` (encrypted) — for Facebook Messenger + Instagram DMs
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

Scheduled jobs call the same loop with a fresh one-shot message (no persistent conversation).

#### Tool System (`app/agent/tools.py`)

14 tools, dispatching to integrations based on tenant config:

| Tool | Dispatches to |
|------|---------------|
| `echo` | — (testing) |
| `create_lead` | HubSpot / Splose / Google Sheets |
| `update_lead` | HubSpot / Splose |
| `search_contacts` | HubSpot / Splose / Google Sheets |
| `check_availability` | Google Calendar / Calendly / Splose |
| `book_appointment` | Google Calendar / Calendly (returns link) / Splose |
| `list_appointments` | Google Calendar / Calendly / Splose |
| `cancel_appointment` | Google Calendar / Calendly / Splose |
| `escalate_to_human` | Slack + Email (Resend) |
| `send_email` | Resend API |
| `search_invoices` | Xero |
| `check_payment_status` | Xero |
| `process_document` | Claude vision (PDF, image, text URL) |
| `call_http` | Pre-configured tenant HTTP endpoints only |

#### Scheduled Automations (`app/agent/scheduler.py`)

APScheduler `AsyncIOScheduler` runs in-process. On startup, loads all enabled `ScheduledJob` rows for active tenants and registers them as cron jobs. Admin CRUD operations update the scheduler in-place.

`ScheduledJob` fields: `name`, `cron_expression` (5-field UTC), `prompt`, `delivery_channel` (email/slack/none), `delivery_target`, `enabled`, `last_run_at`.

#### Custom HTTP Tool (`call_http`)

Configured via `tools_config.http_endpoints` — a list of named endpoint objects with `name`, `url`, `method`, `headers`. The agent can only call pre-configured endpoints; no arbitrary URL access.

#### Client Dashboard (`/client/`)

Read-only performance dashboard for clients. Auth: tenant's own `api_key` via `X-API-Key` header (separate from admin key).

Endpoints: `GET /client/me`, `GET /client/stats`, `GET /client/conversations` (anonymised identifiers).

UI served at `/client/` — single-file vanilla JS, same dark aesthetic as admin dashboard.

#### Webhook Endpoints

- `POST /webhooks/twilio/whatsapp` — Inbound WhatsApp (Twilio signature validated)
- `POST /webhooks/twilio/sms` — Inbound SMS (Twilio signature validated)
- `POST /webhooks/meta` — Facebook Messenger + Instagram DMs (Meta signature validated)
- `POST /webhooks/generic/{tenant_id}` — Web chat / custom (tenant API key auth)

#### Admin Endpoints

All require `X-API-Key: ADMIN_API_KEY`.

- `GET/POST /admin/tenants` — List/create tenants
- `GET/PUT /admin/tenants/{id}` — Get/update tenant
- `GET /admin/tenants/{id}/usage` — Usage stats
- `GET /admin/tenants/{id}/conversations` — Recent conversations
- `GET /admin/tenants/{id}/webhook-errors` — Failed webhook log
- `GET/POST /admin/tenants/{id}/scheduled-jobs` — List/create scheduled jobs
- `GET/PUT/DELETE /admin/tenants/{id}/scheduled-jobs/{job_id}` — Manage job
- `POST /admin/tenants/{id}/scheduled-jobs/{job_id}/run` — Trigger immediate run
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
    cors_origins: str = ""
```

### Security

- Fernet encryption for all tenant credentials at rest
- Twilio signature validation on all inbound WhatsApp/SMS webhooks
- Meta app-secret signature validation on Messenger/Instagram webhooks
- All DB queries scoped by tenant_id
- In-memory sliding window rate limiter on webhook endpoints
- No message content logged in production
- Admin endpoints behind API key auth
- Client dashboard uses tenant's own key (not admin key) — read-only
- `call_http` tool only reaches pre-configured, admin-approved endpoints

### Development Workflow

```bash
docker compose up -d db          # Start Postgres
cp .env.example .env             # Fill in API keys
source .venv/bin/activate        # Python venv at agent-service/.venv
alembic upgrade head             # Run migrations (includes scheduled_jobs table)
uvicorn app.main:app --reload    # Dev server at :8000
pytest                           # 122 tests
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
| Facebook Messenger | `meta_page_id` | `meta_credentials` (JSON: app_secret, page_access_token, verify_token) | Page Access Token |
| Instagram DMs | `meta_page_id` | `meta_credentials` (same as Messenger) | Page Access Token |
| Slack | `escalation_config.slack_webhook_url` | In escalation_config | Incoming Webhook |
| Email (Resend) | `escalation_config.email` | `RESEND_API_KEY` in .env | API key |
| WhatsApp | `twilio_phone_number` | `twilio_account_sid` + `twilio_auth_token` | API key |
| SMS | `twilio_phone_number` | `twilio_account_sid` + `twilio_auth_token` | API key |
| Custom HTTP | `tools_config.http_endpoints` | In endpoint headers (configured per endpoint) | Any |

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
- **No Redis** — in-memory rate limiting, APScheduler, Postgres for everything else
- **APScheduler in-process** — avoids Celery/Redis complexity at this scale; restarts cleanly
- **Splose for allied health** — dominant tool in Australian allied health vertical
- **Client dashboard via tenant API key** — no separate auth system; same key used for webhook auth

---

## Part 3: n8n Workflow Platform

### Overview

For clients who need tool-to-tool automation without a conversational AI agent, RelayAI runs a managed n8n instance. n8n handles workflow automation — Xero triggers, form → CRM, appointment reminders, Slack notifications, etc.

- **n8n instance:** https://n8n.relayai.com.au (admin only — clients never log in)
- **Templates:** `n8n-templates/` in the monorepo root (JSON workflow exports)
- **Client records:** `clients/[slug]/workflows.md`
- **Deployment:** Railway service `n8n` + Railway Postgres `n8n-db`
- **Deployment guide:** `agent-service/docs/deployment.md` (n8n section)

### Delivery track decision

| Signal | Platform |
|---|---|
| Client wants WhatsApp / SMS / web chat bot | AI Agent service |
| Client wants tool-to-tool automation, no conversation | n8n |
| Client needs both | Both — agent service tenant + n8n project, independently configured |

### Client isolation

Each client has their own n8n **Project** named `Client — [Business Name]`. Credentials configured inside a Project are not visible to other Projects. All Projects live on the shared n8n instance.

### Template library

`n8n-templates/` contains JSON workflow exports organised by category:

| Directory | Contents |
|---|---|
| `crm/` | HubSpot contact creation from forms and bookings |
| `accounting/` | Xero invoice triggers |
| `scheduling/` | Appointment reminders and booking confirmations |
| `notifications/` | Slack and email alerting |
| `allied-health/` | Workflows specific to allied health practices |

When onboarding a new n8n client:
1. Create their Project in n8n
2. Import relevant template JSONs
3. Reconnect credentials inside the Project
4. Adapt message copy, schedules, thresholds
5. Activate

Full instructions: `n8n-templates/README.md`

### Client records

Every client (both AI agent and n8n) has a directory under `clients/[slug]/`:
- `discovery.md` — notes from the initial discovery call
- `workflows.md` — active automations, platform, last updated date

See `clients/README.md` for the full convention.
