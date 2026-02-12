# CLAUDE.md — AI Agent Business Project

## Project Overview

This project has two deliverables:

1. **Landing Page** — A single-page marketing site for an AI automation consultancy targeting Adelaide SMBs.
2. **Agent Service** — A multi-tenant FastAPI backend that hosts custom AI agents for multiple clients, handling WhatsApp/webhook inbound, LLM processing with tool use, CRM integration, and outbound messaging.

Both live in a monorepo. The landing page is a static site. The agent service is a containerised Python application.

---

## Repository Structure

```
ai-agent-business/
├── CLAUDE.md
├── landing-page/
│   ├── index.html          # Single-file landing page (HTML + CSS + JS)
│   └── assets/             # Favicon, OG image, any static assets
├── agent-service/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── alembic/             # DB migrations
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py          # FastAPI app entry point, lifespan, CORS
│   │   ├── config.py        # Pydantic Settings, env var loading
│   │   ├── database.py      # Async SQLAlchemy engine + session factory
│   │   ├── models/          # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── tenant.py    # Tenant config, credentials, system prompt
│   │   │   ├── conversation.py  # Conversation history per end-user
│   │   │   └── usage.py     # Token usage tracking per tenant
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── webhook.py
│   │   │   └── tenant.py
│   │   ├── routers/         # FastAPI routers
│   │   │   ├── __init__.py
│   │   │   ├── webhooks.py  # Inbound webhook endpoints (WhatsApp, generic)
│   │   │   ├── tenants.py   # Tenant CRUD (admin only)
│   │   │   └── health.py    # Health check endpoint
│   │   ├── agent/           # Core agent logic
│   │   │   ├── __init__.py
│   │   │   ├── loop.py      # The agent loop: message → LLM → tool exec → reply
│   │   │   ├── tools.py     # Tool registry and execution dispatcher
│   │   │   └── prompts.py   # System prompt builder per tenant
│   │   ├── integrations/    # External service clients
│   │   │   ├── __init__.py
│   │   │   ├── anthropic.py # Claude API client wrapper
│   │   │   ├── twilio.py    # Twilio WhatsApp send/receive
│   │   │   ├── hubspot.py   # HubSpot CRM client
│   │   │   └── google_sheets.py  # Google Sheets fallback CRM
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   └── auth.py      # API key auth for admin endpoints
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── logging.py   # Structured logging config
│   └── tests/
│       ├── conftest.py      # Fixtures: test DB, mock clients, tenant factory
│       ├── test_agent_loop.py
│       ├── test_webhooks.py
│       ├── test_tools.py
│       └── test_integrations/
│           ├── test_twilio.py
│           └── test_hubspot.py
```

---

## Part 1: Landing Page

### Tech

Single HTML file. No framework, no build step. HTML + CSS + minimal vanilla JS for smooth scroll and a contact form submission (posts to a Formspree/Netlify Forms endpoint or the agent-service itself).

### Design Direction

Do NOT make this look like a generic AI/SaaS template. No purple gradients, no "Inter" font, no stock illustrations of robots.

**Aesthetic**: Industrial-clean. Think professional trades workshop — functional, confident, no-nonsense. Dark background (near-black or deep charcoal), warm accent colour (amber/gold or burnt orange), strong sans-serif display font (e.g., "Instrument Sans", "General Sans", "Satoshi", or "Clash Display" from Fontshare), clean body font (e.g., "Switzer" or "Cabinet Grotesk").

**Layout structure** (single page, scroll):

1. **Hero** — Bold headline focused on outcome, not technology. Example: "Your Business, Running While You Sleep." Subheadline explains the what (AI agents that handle enquiries, qualify leads, book jobs 24/7). Single CTA button: "Book a Free Consultation". No hero image — use a subtle animated grain/noise texture or geometric pattern for atmosphere.

2. **How It Works** — 3 steps, horizontal on desktop, stacked on mobile. Keep it dead simple: "We learn your business → We build your agent → It works for you 24/7." Use numbered steps with short descriptions. No icons unless they're custom/distinctive.

3. **What It Does** — 3-4 use case cards. Each card: short headline, 2-sentence description, no bullet points. Examples: "Never Miss a Lead", "Qualify Before You Call Back", "Automate the Back-and-Forth". Cards should have a subtle hover effect (slight lift + border glow in accent colour).

4. **Who It's For** — Short section listing target industries: tradies, real estate, clinics, professional services. One line each. No elaborate descriptions.

5. **Pricing** — 2-3 tier cards. Starter / Growth / Custom. Show monthly price, conversation limit, what's included. Keep it transparent — this builds trust with SMBs. "Custom" tier says "Let's talk" instead of a price.

6. **CTA / Contact** — Repeat the primary CTA. Simple form: name, email, business type (dropdown), message. Submit posts to backend or Formspree.

7. **Footer** — ABN, email, phone, LinkedIn. Minimal.

**Technical requirements**:
- Mobile-first responsive. Must look good on iPhone Safari.
- Fast — no heavy assets. Target < 200KB total page weight.
- Fonts loaded from Google Fonts or Fontshare CDN.
- Smooth scroll behaviour for anchor links.
- Form validation with vanilla JS.
- Meta tags for SEO: title, description, OG tags.
- Semantic HTML (proper heading hierarchy, landmarks).

### What NOT to do on the landing page
- No chatbot widget on the landing page itself (ironic but distracting)
- No "AI" in the hero headline — focus on the outcome, not the tech
- No testimonials section if there are no real testimonials yet — a placeholder with fake ones destroys trust
- No animations that delay content visibility (no loading screens, no reveal-on-scroll for critical content)

---

## Part 2: Agent Service (FastAPI)

### Tech Stack

- **Python 3.12+**
- **FastAPI** with async throughout
- **SQLAlchemy 2.0** (async) with PostgreSQL
- **Alembic** for migrations
- **Anthropic Python SDK** for Claude API
- **Twilio Python SDK** for WhatsApp
- **httpx** for async HTTP calls to CRM APIs
- **Pydantic v2** for all schemas and settings
- **Docker + Docker Compose** for local dev and deployment

### Core Concepts

#### Multi-Tenancy

Every tenant (client business) is a row in the `tenants` table. All queries are scoped by `tenant_id`. There is no separate database per tenant — single DB, row-level isolation.

A tenant record contains:
- `id` (UUID)
- `name` (business name)
- `twilio_phone_number` (their WhatsApp number — used to route inbound messages)
- `system_prompt` (the LLM system prompt for this tenant's agent)
- `tools_config` (JSON — which tools are enabled and their configuration)
- `crm_type` (enum: hubspot, google_sheets, none)
- `crm_credentials` (encrypted JSON — API keys, sheet IDs, etc.)
- `twilio_account_sid` / `twilio_auth_token` (encrypted)
- `escalation_config` (JSON — where to send escalations: Slack webhook, email, etc.)
- `max_conversations_per_month` (usage cap)
- `is_active` (boolean)
- `created_at` / `updated_at`

#### The Agent Loop

This is the core of the system. Located in `app/agent/loop.py`.

```
receive message
    → load tenant config
    → load conversation history for (tenant_id, sender_phone)
    → append user message to history
    → LOOP:
        → call Claude API with (system_prompt, tools, history)
        → if stop_reason == "end_turn":
            → extract text response
            → save updated history
            → return response text
        → if stop_reason == "tool_use":
            → for each tool_use block:
                → execute tool via dispatcher
                → append tool_result to history
            → continue loop (let LLM see tool results)
```

Important constraints:
- **Max loop iterations**: Cap at 5 to prevent runaway tool-calling. If the agent hasn't resolved after 5 tool calls, force a text response.
- **Timeout**: 30-second overall timeout on the agent loop. WhatsApp has delivery expectations — a reply that takes 2 minutes feels broken.
- **Error handling**: If a tool call fails (CRM API down, invalid args), return an error message as the tool_result so the LLM can gracefully handle it ("I'm having trouble saving your details right now, let me take your info and someone will follow up").

#### Tool System

Tools are defined per-tenant but drawn from a shared registry. Located in `app/agent/tools.py`.

The tool registry maps tool names to:
1. The Anthropic tool schema (name, description, input_schema)
2. An async execution function

Available tools (implement incrementally):
- `create_lead` — Creates a contact/lead in the tenant's CRM
- `update_lead` — Updates an existing lead with new info
- `search_contacts` — Checks if this phone number already exists in the CRM
- `check_availability` — Queries available booking slots (if tenant has a booking system)
- `escalate_to_human` — Sends a notification to the tenant (Slack, email, SMS) with conversation summary
- `search_knowledge_base` — RAG search against tenant's embedded documents (future, not MVP)

Each tool function receives the tenant config so it knows which CRM to hit, what credentials to use, etc.

```python
async def execute_tool(
    tool_name: str,
    tool_input: dict,
    tenant: Tenant,
) -> str:
    handler = TOOL_REGISTRY.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = await handler(tool_input, tenant)
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name}", exc_info=True)
        return json.dumps({"error": "Tool execution failed", "detail": str(e)})
```

#### Conversation Storage

Table: `conversations`
- `id` (UUID)
- `tenant_id` (FK)
- `external_identifier` (the sender's phone number or channel-specific ID)
- `channel` (enum: whatsapp, web, sms)
- `messages` (JSONB — the full conversation history in Anthropic message format)
- `status` (enum: active, escalated, closed)
- `metadata` (JSONB — any extracted info like name, lead score, etc.)
- `created_at` / `updated_at`
- `last_message_at`

Index on `(tenant_id, external_identifier)` for fast lookups.

Conversation history is stored as the raw Anthropic messages array so it can be passed directly back to the API without transformation. Include both user messages, assistant responses, and tool_use/tool_result blocks.

#### Usage Tracking

Table: `usage_logs`
- `id` (UUID)
- `tenant_id` (FK)
- `conversation_id` (FK)
- `input_tokens` (int)
- `output_tokens` (int)
- `model` (string)
- `estimated_cost_usd` (decimal)
- `created_at`

Log every LLM API call. This is critical for understanding per-tenant costs and enforcing usage caps.

#### Webhook Endpoints

**WhatsApp (Twilio)**:
- `POST /webhooks/twilio/whatsapp` — Receives inbound messages. Twilio sends form-encoded data. Validate the request signature using Twilio's `RequestValidator` to prevent spoofing. Extract the `To` number to identify the tenant, `From` for the sender, `Body` for the message. Run the agent loop. Send the reply via Twilio API.

**Generic webhook** (for future channels):
- `POST /webhooks/generic/{tenant_id}` — JSON body with `sender_id` and `message`. Authenticated with a per-tenant API key. Returns the agent's response as JSON. This is useful for web chat widgets or custom integrations.

#### Admin Endpoints

Protected by API key auth (middleware checks `X-API-Key` header against an admin key in env vars). These are for you to manage tenants, not for clients.

- `GET /admin/tenants` — List all tenants
- `POST /admin/tenants` — Create a tenant
- `GET /admin/tenants/{id}` — Get tenant details
- `PUT /admin/tenants/{id}` — Update tenant config (system prompt, tools, CRM creds)
- `GET /admin/tenants/{id}/usage` — Get usage stats for a tenant (total tokens, cost, conversation count)
- `GET /admin/tenants/{id}/conversations` — List recent conversations for a tenant

### Configuration (app/config.py)

Use Pydantic Settings to load from environment variables:

```python
class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str
    default_model: str = "claude-sonnet-4-5-20250514"
    admin_api_key: str
    twilio_account_sid: str  # fallback if tenant doesn't have their own
    twilio_auth_token: str
    log_level: str = "INFO"
    max_agent_iterations: int = 5
    agent_timeout_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env")
```

### Docker Compose (local dev)

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
    volumes:
      - ./app:/app/app  # hot reload in dev

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: agents
      POSTGRES_USER: agents
      POSTGRES_PASSWORD: localdev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

### Testing Strategy

- **Unit tests**: Test the agent loop with mocked LLM responses (return predetermined tool_use and text blocks). Test tool execution with mocked HTTP clients. Test tenant routing logic.
- **Integration tests**: Use a test Postgres instance (Docker). Test the full webhook → agent → CRM flow with mocked external APIs.
- **No mocking the LLM in integration tests**: For true end-to-end testing, have a small test budget to call the real Claude API with a test tenant. This catches prompt regressions.
- Use `pytest` with `pytest-asyncio`. Use `httpx.AsyncClient` for testing FastAPI endpoints.

Fixtures in `conftest.py` should provide:
- A test database session (transaction-rolled-back per test)
- A factory function to create test tenants with sensible defaults
- Mock Twilio and CRM clients that record calls instead of making real HTTP requests

### Security Considerations

- **Encrypt tenant credentials at rest.** CRM API keys and Twilio tokens stored in the DB should be encrypted using Fernet or similar. Decrypt at runtime only when needed.
- **Validate Twilio webhook signatures.** Every inbound WhatsApp request must pass Twilio's signature validation. Reject unsigned requests.
- **Scope all DB queries by tenant_id.** Never allow cross-tenant data access. This is the most important invariant in the system.
- **Rate limit inbound webhooks.** Prevent abuse. Use a simple in-memory rate limiter or Redis if available.
- **Don't log message content in production.** Log metadata (tenant_id, conversation_id, token counts) but not the actual message bodies. SMB client data is sensitive.
- **Admin endpoints behind API key auth.** Not exposed publicly. Consider restricting to specific IP ranges in production.

### Deployment (Production)

Target: Single VPS (Hetzner CPX11 or similar, Sydney region, ~$10-20/month AUD).

- Docker Compose with the app container + Postgres (or use a managed Postgres like Supabase/Neon).
- Caddy as reverse proxy for automatic TLS.
- Systemd service to ensure Docker Compose restarts on reboot.
- Daily Postgres backups to object storage (Hetzner Object Storage or Backblaze B2).
- UptimeRobot (free) monitoring the `/health` endpoint.
- Sentry for error tracking (free tier is sufficient).

### Development Workflow

1. Clone repo, copy `.env.example` to `.env`, fill in API keys
2. `docker compose up -d db` to start Postgres
3. `alembic upgrade head` to run migrations
4. `uvicorn app.main:app --reload` to start the dev server
5. `ngrok http 8000` to get a public URL for Twilio webhook testing
6. Configure Twilio sandbox webhook to point at ngrok URL
7. Message the sandbox WhatsApp number from your phone
8. Watch it work

---

## Implementation Order

Build in this order. Each step produces something testable.

### Phase 1: Foundation
1. Project scaffolding (pyproject.toml, Dockerfile, docker-compose.yml)
2. Database models and Alembic migrations
3. Config and settings
4. Health check endpoint
5. Admin CRUD for tenants

### Phase 2: Agent Core
6. Anthropic client wrapper (handles API calls, retries, token counting)
7. Tool registry with a single dummy tool (e.g., `echo` that just returns its input)
8. The agent loop (the core while loop with tool execution)
9. Unit tests for the agent loop with mocked LLM responses

### Phase 3: WhatsApp Integration
10. Twilio webhook endpoint (receive, validate signature, parse)
11. Conversation storage (load/save history from Postgres)
12. Twilio outbound (send reply back)
13. End-to-end test: message WhatsApp → get intelligent reply

### Phase 4: CRM Integration
14. HubSpot client (create_contact, search_contacts)
15. Google Sheets client (append_row) as fallback CRM
16. Wire up `create_lead` and `search_contacts` tools
17. End-to-end test: WhatsApp conversation → lead appears in HubSpot

### Phase 5: Production Readiness
18. Usage tracking (log tokens per API call, aggregate per tenant)
19. Credential encryption for tenant secrets
20. Structured logging
21. Error handling and graceful degradation
22. Rate limiting on webhook endpoints
23. Deploy to VPS with Caddy + Docker Compose

### Phase 6: Landing Page
24. Build the landing page (single HTML file)
25. Deploy to Netlify/Cloudflare Pages (separate from the agent service)
26. Connect contact form to either Formspree or a webhook on the agent service

---

## Key Design Decisions

- **Sonnet over Opus for agent tasks.** Sonnet is fast enough for real-time chat and significantly cheaper. Use Opus only if a tenant needs complex reasoning (rare for SMB use cases).
- **No LangChain / LangGraph.** The agent loop is simple enough that a framework adds dependency overhead without meaningful benefit. Build it from scratch with the raw Anthropic SDK.
- **JSONB for conversation history.** Store the raw Anthropic message format. Avoids lossy transformations and means history can be replayed directly. PostgreSQL JSONB is fast enough for this access pattern.
- **Single service, not microservices.** At 10-30 tenants, there is no reason to split this into multiple services. One FastAPI app handles everything. Split later if a specific component needs independent scaling (unlikely at this stage).
- **No Redis initially.** Conversation history comes from Postgres. Rate limiting can be in-memory. Add Redis later if you need pub/sub for real-time features or if rate limiting needs to be distributed.
