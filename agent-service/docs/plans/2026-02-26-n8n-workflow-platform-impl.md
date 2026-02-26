# n8n Workflow Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy a managed n8n instance on Railway, build a starter template library, and update all project documentation to reflect the new delivery track.

**Architecture:** Single n8n Railway service with its own Postgres database. n8n Projects for per-client isolation. Template JSONs version-controlled in the monorepo under `n8n-templates/`. No code changes to the agent service.

**Tech Stack:** n8n (Docker), Railway, Postgres, JSON workflow exports.

---

### Task 1: Create n8n-templates/ directory structure and README

**Files:**
- Create: `n8n-templates/README.md`
- Create: `n8n-templates/crm/.gitkeep`
- Create: `n8n-templates/accounting/.gitkeep`
- Create: `n8n-templates/scheduling/.gitkeep`
- Create: `n8n-templates/notifications/.gitkeep`
- Create: `n8n-templates/allied-health/.gitkeep`

**Step 1: Create the directory tree**

```bash
mkdir -p n8n-templates/{crm,accounting,scheduling,notifications,allied-health}
touch n8n-templates/{crm,accounting,scheduling,notifications,allied-health}/.gitkeep
```

Run from repo root: `/home/ben/Projects/agent-biz/`

**Step 2: Write `n8n-templates/README.md`**

```markdown
# n8n Workflow Templates

Reusable n8n workflow exports for common Australian SMB automation patterns.
Each file is a JSON export that can be imported directly into n8n.

## How to use a template

1. In n8n, open the target client Project
2. Click **"Add workflow"** → **"Import from file"**
3. Select the relevant `.json` file from this directory
4. n8n will prompt you to reconnect credentials — do this inside the client Project
5. Adapt any hardcoded values (email addresses, thresholds, message copy)
6. Test with real data using the n8n manual trigger
7. Activate

## Directory structure

| Directory | Contents |
|---|---|
| `crm/` | Workflows that create or update CRM contacts (HubSpot) |
| `accounting/` | Xero-triggered workflows (invoices, payments) |
| `scheduling/` | Appointment reminders and booking confirmations |
| `notifications/` | Generic alerting workflows (Slack, email) |
| `allied-health/` | Workflows specific to physio/OT/psychology practices |

## Exporting a workflow as a template

1. Open the workflow in n8n
2. Click the three-dot menu → **"Download"**
3. Save the JSON to the appropriate subdirectory
4. Before committing, open the JSON and replace any real client data
   (email addresses, phone numbers, API endpoints) with placeholders like
   `YOUR_EMAIL_HERE`, `YOUR_XERO_ACCOUNT_ID`, etc.
5. Commit with message: `feat(n8n): add [workflow name] template`

## Credential placeholders

When a credential node appears in an exported workflow, n8n replaces the
actual secret with a reference ID. On import into a new instance, n8n will
ask you to reconnect — this is expected and correct. You do not need to
manually redact credentials from the JSON.

## Client isolation

Each client's workflows live in their own n8n **Project**:
`Client — [Business Name]`

Credentials configured inside a Project are not visible to other Projects.
```

**Step 3: Commit**

```bash
git add n8n-templates/
git commit -m "feat: add n8n-templates directory structure and README"
```

---

### Task 2: Deploy n8n on Railway

No code changes — this is infrastructure work done in the Railway dashboard.

**Step 1: Add a new Postgres database to the Railway project**

1. Open [railway.app](https://railway.app) → your project
2. Click **"+ New"** → **"Database"** → **"PostgreSQL"**
3. Name it `n8n-db`
4. Copy the **internal** connection string — you'll need the host, port, user, password, and database name separately (Railway shows these as individual variables)

**Step 2: Add a new Railway service for n8n**

1. Click **"+ New"** → **"Docker Image"**
2. Image: `n8nio/n8n:latest`
3. Name the service `n8n`

**Step 3: Set environment variables on the n8n service**

In the n8n service → Variables, add:

| Variable | Value |
|---|---|
| `N8N_BASIC_AUTH_ACTIVE` | `true` |
| `N8N_BASIC_AUTH_USER` | `admin` |
| `N8N_BASIC_AUTH_PASSWORD` | Generate: `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` |
| `N8N_ENCRYPTION_KEY` | Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `WEBHOOK_URL` | `https://n8n.relayai.com.au` (set after domain is configured) |
| `N8N_RUNNERS_ENABLED` | `true` |
| `DB_TYPE` | `postgresdb` |
| `DB_POSTGRESDB_HOST` | Internal host from n8n-db (Railway internal hostname) |
| `DB_POSTGRESDB_PORT` | `5432` |
| `DB_POSTGRESDB_DATABASE` | `railway` |
| `DB_POSTGRESDB_USER` | `postgres` |
| `DB_POSTGRESDB_PASSWORD` | From n8n-db service variables |
| `GENERIC_TIMEZONE` | `Australia/Adelaide` |
| `N8N_DEFAULT_LOCALE` | `en` |

**Step 4: Configure custom domain**

1. In the n8n Railway service → Settings → Networking → Custom Domain
2. Add `n8n.relayai.com.au`
3. Add the CNAME record to your DNS provider pointing to the Railway-provided hostname
4. Wait for SSL to provision (usually < 5 minutes)

**Step 5: Verify deployment**

Navigate to `https://n8n.relayai.com.au` — you should see the n8n login screen.
Log in with the `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD` you set.

**Step 6: Create the internal project**

1. In n8n → top-left dropdown → **"+ New project"**
2. Name: `RelayAI Internal`
3. This is where you'll build and test templates before exporting them

**Step 7: Update deployment.md**

Add an "n8n Deployment" section to `agent-service/docs/deployment.md` with the env var table and domain setup steps above.

---

### Task 3: Build and export the first 4 templates

Build these in n8n under `RelayAI Internal`, test them with mock data, export as JSON, commit.

**Order (simplest → most complex):**

#### 3a. `notifications/web-form-to-email-slack.json`

Trigger: Webhook node (POST)
Action 1: Send email via Gmail/Resend
Action 2: Post to Slack

Placeholder values to replace before committing:
- Webhook path (n8n generates this — leave as-is, it's not sensitive)
- Slack webhook URL → `YOUR_SLACK_WEBHOOK_URL`
- Email to address → `YOUR_NOTIFICATION_EMAIL`

#### 3b. `crm/form-to-hubspot.json`

Trigger: Webhook node (POST, expects JSON with `name`, `email`, `phone`, `message`)
Action: HubSpot → Create Contact node

Placeholder: HubSpot credential reference (n8n handles this on import)

#### 3c. `crm/calendly-to-hubspot.json`

Trigger: Webhook node (Calendly sends POST on booking)
Action 1: Extract invitee name/email from Calendly payload
Action 2: HubSpot → Create/Update Contact

Note: Calendly webhook payload path is `payload.invitee.name` / `payload.invitee.email`.

#### 3d. `accounting/xero-new-invoice-notification.json`

Trigger: Webhook node (Xero webhook on invoice create)
Action: Slack or email notification with invoice amount and contact name

Note: Xero webhooks require signature validation — use an n8n Respond to Webhook node to return 200 immediately, then validate `x-xero-signature` header.

**Step 1: Build each workflow in n8n RelayAI Internal**

Manual — work through each one in the n8n UI.

**Step 2: Test with manual trigger**

Use n8n's "Test workflow" button with mock payloads for each webhook trigger.

**Step 3: Export each workflow**

Three-dot menu → Download → save to `n8n-templates/<category>/<name>.json`

**Step 4: Commit**

```bash
git add n8n-templates/
git commit -m "feat(n8n): add initial 4 workflow templates"
```

---

### Task 4: Update `docs/client-onboarding.md`

Add an n8n track section so the onboarding doc covers both delivery paths.

**Files:**
- Modify: `agent-service/docs/client-onboarding.md`

**Step 1: Add section after the existing Quick-Start Checklist**

Insert the following section immediately after the closing `---` of the Quick-Start Checklist:

```markdown
## Delivery Tracks

RelayAI delivers automation via two tracks. Use the right one for each client.

| Track | When to use | Time to deliver |
|---|---|---|
| **AI Agent** (this doc) | Client needs conversational automation — WhatsApp bot, lead qualification, appointment booking via chat, 24/7 customer response | 1–2 weeks |
| **n8n Workflow** (see below) | Client needs tool-to-tool automation — Xero triggers, form → CRM, appointment reminders, Slack notifications. No conversation required. | 30–60 min per workflow |

Most clients need one or the other, not both. If they ask "can it reply to WhatsApp messages?" → AI agent. If they ask "can it automatically send an invoice reminder?" → n8n.

---

## n8n Track: Onboarding Checklist

- [ ] Discovery call — identify which n8n templates apply
- [ ] Create n8n Project: `Client — [Business Name]` at https://n8n.relayai.com.au
- [ ] Import relevant templates from `n8n-templates/` directory
- [ ] Configure credentials inside the Project (Xero OAuth, HubSpot key, etc.)
- [ ] Adapt message copy, email addresses, thresholds to client specifics
- [ ] Test end-to-end with real data using n8n manual trigger
- [ ] Activate workflows
- [ ] Create `clients/[client-slug]/workflows.md` documenting what's running
- [ ] Check in with client after 1 week — workflows running as expected?

See `n8n-templates/README.md` for how to import templates and manage credentials.
```

**Step 2: Commit**

```bash
git add agent-service/docs/client-onboarding.md
git commit -m "docs: add n8n delivery track to client onboarding guide"
```

---

### Task 5: Update `docs/deployment.md` with n8n section

**Files:**
- Modify: `agent-service/docs/deployment.md`

**Step 1: Append n8n deployment section to the end of the file**

```markdown
---

## n8n Deployment (Workflow Automation Track)

n8n runs as a separate Railway service alongside the agent service.
Access it at: https://n8n.relayai.com.au (admin credentials in 1Password/your password manager).

### Railway service name: `n8n`
### Database: `n8n-db` (separate Postgres — do not share with agent-db)

### Environment variables

| Variable | Notes |
|---|---|
| `N8N_BASIC_AUTH_ACTIVE` | `true` |
| `N8N_BASIC_AUTH_USER` | `admin` |
| `N8N_BASIC_AUTH_PASSWORD` | In password manager |
| `N8N_ENCRYPTION_KEY` | In password manager — DO NOT rotate without migrating credentials |
| `WEBHOOK_URL` | `https://n8n.relayai.com.au` |
| `N8N_RUNNERS_ENABLED` | `true` |
| `DB_TYPE` | `postgresdb` |
| `DB_POSTGRESDB_*` | Connection details from n8n-db Railway service |
| `GENERIC_TIMEZONE` | `Australia/Adelaide` |

### ⚠️ Critical: N8N_ENCRYPTION_KEY

n8n uses this key to encrypt all stored credentials (OAuth tokens, API keys, etc.).
If you rotate or lose it, all stored credentials become unrecoverable — you will need
to reconnect every integration for every client. Store it in a password manager and
never change it without a migration plan.

### Upgrading n8n

Railway will auto-deploy on `n8nio/n8n:latest` pushes if you have auto-deploy enabled.
To pin a version (recommended for stability), change the image to `n8nio/n8n:1.x.x`.
Always check the [n8n changelog](https://github.com/n8n-io/n8n/releases) before upgrading
— breaking changes do occur between minor versions.
```

**Step 2: Commit**

```bash
git add agent-service/docs/deployment.md
git commit -m "docs: add n8n Railway deployment guide"
```

---

### Task 6: Create `clients/` directory convention and update existing client record

**Files:**
- Create: `clients/README.md`
- Verify: `clients/prosper-wealth/discovery.md` exists (it does — check and update if needed)
- Create: `clients/prosper-wealth/workflows.md`

**Step 1: Write `clients/README.md`**

```markdown
# Clients

One directory per client. Slug format: lowercase, hyphens, no spaces.

## Directory structure

```
clients/
└── client-slug/
    ├── discovery.md    Notes from discovery call — business context, pain points, requirements
    └── workflows.md    Active automations — what is running, on which platform, last updated
```

## Active clients

| Client | Slug | Platform | Status |
|---|---|---|---|
| Prosper Wealth | `prosper-wealth` | TBD | Discovery |

Update this table when a client goes live.
```

**Step 2: Create `clients/prosper-wealth/workflows.md`**

```markdown
# Prosper Wealth — Active Workflows

**Platform:** TBD (pending discovery)
**Status:** Discovery phase
**Last updated:** 2026-02-26

## Active automations

None yet — in discovery.

## Notes

See `discovery.md` for context from the initial discovery call.
```

**Step 3: Commit**

```bash
git add clients/
git commit -m "docs: add clients directory convention and prosper-wealth workflow record"
```

---

### Task 7: Update CLAUDE.md to reflect n8n platform

**Files:**
- Modify: `/home/ben/Projects/agent-biz/CLAUDE.md`

**Step 1: Add n8n section to the Repository Structure block and a new Part 3 section**

After the `landing-page/` and before `agent-service/` in the structure, add:

```
├── n8n-templates/          # Reusable n8n workflow JSON exports (see README inside)
├── clients/                # Per-client records (discovery notes, active workflows)
```

Then add a new section at the end of CLAUDE.md:

```markdown
---

## Part 3: n8n Workflow Platform

### Overview

For clients who need tool-to-tool automation without a conversational AI agent, RelayAI runs a managed n8n instance. n8n handles workflow automation — Xero triggers, form → CRM, appointment reminders, Slack notifications, etc.

- **n8n instance:** https://n8n.relayai.com.au (admin only — clients never log in)
- **Templates:** `n8n-templates/` in the monorepo root
- **Client records:** `clients/[slug]/workflows.md`
- **Deployment:** Railway service `n8n` + Railway Postgres `n8n-db`

### Delivery decision

| Signal | Platform |
|---|---|
| Client wants WhatsApp/SMS/web chat bot | AI Agent service |
| Client wants tool-to-tool automation, no conversation | n8n |
| Client wants both | Both — separate tenants/projects |

### Client isolation

Each client has their own n8n **Project** (`Client — [Business Name]`). Credentials inside a Project are not visible to other Projects.

### Template library

`n8n-templates/` contains JSON workflow exports organised by category. When onboarding a new n8n client:
1. Identify which templates apply
2. Import into their Project in n8n
3. Reconnect credentials inside the Project
4. Adapt and activate

See `n8n-templates/README.md` for full import/export instructions.
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add n8n workflow platform to CLAUDE.md"
```

---

## Execution order

Tasks 1 → 2 → 3 → 4 → 5 → 6 → 7

Tasks 1, 4, 5, 6, 7 are pure documentation/repo work — fast.
Task 2 is Railway infrastructure — requires browser access to Railway dashboard.
Task 3 requires n8n to be deployed (depends on Task 2) and is the most time-consuming.

## Definition of done

- [ ] `n8n-templates/` directory committed with README and subdirectories
- [ ] n8n running at `https://n8n.relayai.com.au`
- [ ] `RelayAI Internal` project exists in n8n
- [ ] 4 starter templates committed as JSON exports
- [ ] `docs/client-onboarding.md` covers both AI agent and n8n tracks
- [ ] `docs/deployment.md` covers n8n Railway deployment
- [ ] `clients/README.md` exists with convention documented
- [ ] `CLAUDE.md` updated to reflect n8n platform
