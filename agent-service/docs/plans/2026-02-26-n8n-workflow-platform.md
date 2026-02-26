# n8n Workflow Platform Design

**Date:** 2026-02-26
**Status:** Approved

---

## Problem

Some clients need business automation without requiring an AI agent — simple, reliable workflow automation connecting tools they already use. Building these bespoke each time, from scratch, is slow and unscalable. We need a managed n8n deployment and a reusable template library to deliver these jobs quickly.

---

## Decision

Deploy a single self-hosted n8n instance on Railway. Use n8n Projects for per-client isolation. Maintain a library of reusable workflow JSON templates in the monorepo. When a no-code automation client comes on, pick the relevant templates, import them into their project, configure credentials, activate.

This is **not** a replacement for the AI agent service — it is a parallel delivery track for clients whose requirements don't warrant an agent.

---

## Infrastructure

Single n8n Railway service alongside the existing agent service:

```
Railway project
├── agent-service          (existing)
├── agent-db               (existing Postgres)
├── n8n                    (new — Docker image: n8nio/n8n:latest)
└── n8n-db                 (new Postgres — separate from agent-db)
```

- Public URL: `n8n.relayai.com.au`
- Auth: HTTP Basic Auth (admin only — clients never log in)
- n8n version: latest stable (pin in deployment)
- Encryption key: stored as Railway env var `N8N_ENCRYPTION_KEY`

**Required Railway env vars:**

| Variable | Notes |
|---|---|
| `N8N_BASIC_AUTH_ACTIVE` | `true` |
| `N8N_BASIC_AUTH_USER` | `admin` |
| `N8N_BASIC_AUTH_PASSWORD` | Strong random password |
| `WEBHOOK_URL` | `https://n8n.relayai.com.au` |
| `N8N_ENCRYPTION_KEY` | Random 32-char key — protects stored credentials |
| `DB_TYPE` | `postgresdb` |
| `DB_POSTGRESDB_HOST` | Railway internal Postgres host |
| `DB_POSTGRESDB_PORT` | `5432` |
| `DB_POSTGRESDB_DATABASE` | `railway` |
| `DB_POSTGRESDB_USER` | `postgres` |
| `DB_POSTGRESDB_PASSWORD` | From Railway Postgres service |
| `N8N_RUNNERS_ENABLED` | `true` (required in n8n 1.x+) |

---

## Client Isolation

n8n Projects (v1.0+) provide namespace isolation with separate credential stores per project. No client can see another client's credentials or workflows.

**Project naming convention:**
```
Client — [Business Name]
```

**Workflow naming convention within a project:**
```
[Category] — [Trigger] → [Action]

Examples:
  Xero — Invoice Overdue → Email Reminder
  Calendly — New Booking → HubSpot Contact
  Forms — Typeform Submission → Slack Notification
```

**Internal project for testing:**
```
RelayAI Internal
```

---

## Template Library

Stored at `n8n-templates/` in the monorepo root. Each template is an n8n workflow JSON export with placeholder credentials (n8n will prompt to reconnect credentials on import).

### Directory structure

```
n8n-templates/
├── README.md
├── crm/
│   ├── form-to-hubspot.json
│   └── calendly-to-hubspot.json
├── accounting/
│   ├── xero-overdue-invoice-reminder.json
│   └── xero-new-invoice-notification.json
├── scheduling/
│   ├── appointment-reminder-24h.json
│   └── new-booking-welcome-email.json
├── notifications/
│   ├── google-sheets-row-to-slack.json
│   └── web-form-to-email-slack.json
└── allied-health/
    ├── new-patient-welcome-sequence.json
    └── recall-reminder-overdue-appointment.json
```

### Initial template set (Phase 1)

| Template | Trigger | Action | Target vertical |
|---|---|---|---|
| `crm/form-to-hubspot` | Webhook (web form) | Create HubSpot contact | All |
| `crm/calendly-to-hubspot` | Calendly booking | Create/update HubSpot contact | All |
| `accounting/xero-overdue-invoice-reminder` | Xero — invoice overdue | Send email to client | Trades, professional services |
| `accounting/xero-new-invoice-notification` | Xero — invoice created | Slack/email notification to owner | All |
| `scheduling/appointment-reminder-24h` | Schedule (cron) | Email/SMS reminder 24h before appointment | Allied health, professional services |
| `scheduling/new-booking-welcome-email` | Calendly booking | Send welcome email | All |
| `notifications/google-sheets-row-to-slack` | Google Sheets — new row | Slack notification | All |
| `notifications/web-form-to-email-slack` | Webhook | Email + Slack | All |
| `allied-health/new-patient-welcome-sequence` | Webhook / Splose | Email welcome sequence | Allied health |
| `allied-health/recall-reminder` | Schedule (cron) | Email/SMS recall reminder | Allied health |

---

## Client Onboarding Flow (n8n track)

1. Discovery call — identify which templates apply
2. Create n8n Project: `Client — [Business Name]`
3. Import relevant template JSONs into the project
4. Configure credentials (Xero OAuth, HubSpot key, etc.) inside the project
5. Adapt workflow logic as needed (thresholds, message copy, etc.)
6. Test end-to-end with real data
7. Activate workflows
8. Record client in `clients/` directory (see below)

Target onboarding time per workflow: 30–60 minutes.

---

## Client Records

Each client gets a directory in `clients/[client-slug]/` containing:

```
clients/
└── acme-physio/
    ├── discovery.md       (notes from discovery call)
    └── workflows.md       (which n8n workflows are active, last updated)
```

This is the source of truth for "what is running for which client".

---

## Documentation Updates Required

- `docs/deployment.md` — add n8n Railway deployment steps
- `docs/client-onboarding.md` — add n8n track as an alternative to the AI agent track
- `n8n-templates/README.md` — how to import templates and configure credentials

---

## What This Is Not

- **Not a replacement for the AI agent service.** Clients with conversational requirements (WhatsApp bots, lead qualification, appointment booking via chat) use the agent service.
- **Not a product clients interact with.** n8n is an internal operations tool. Clients never see it.
- **Not multi-tenant SaaS.** This is a managed service — we build and maintain workflows on behalf of clients.
