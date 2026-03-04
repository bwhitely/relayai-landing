# n8n Workflow Templates

Reusable n8n workflow exports for common Australian SMB automation patterns.
Each file is a JSON export that can be imported directly into n8n.

## How to use a template

1. In n8n, click **"Add workflow"** → **"Import from file"**
2. Select the relevant `.json` file from this directory
3. n8n will prompt you to reconnect credentials — select the correct named credential for the client (e.g. `Acme Physio — HubSpot`)
4. Apply the client's tag immediately after import
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
| `outreach/` | Outbound lead sequencing, personalization, and send workflows |
| `allied-health/` | Workflows specific to physio/OT/psychology practices |

## Template index

> **Note:** The templates listed below are planned. JSON files will be added as they are built and tested in n8n. See "Exporting a workflow as a template" below for how to contribute new templates.

| Template | Trigger | Action | Vertical |
|---|---|---|---|
| `crm/form-to-hubspot.json` | Webhook (web form POST) | Create HubSpot contact | All |
| `crm/calendly-to-hubspot.json` | Calendly booking webhook | Create/update HubSpot contact | All |
| `accounting/xero-overdue-invoice-reminder.json` | Xero — invoice overdue | Email reminder to client | Trades, professional services |
| `accounting/xero-new-invoice-notification.json` | Xero — invoice created | Slack/email to owner | All |
| `scheduling/appointment-reminder-24h.json` | Cron (daily) | Email/SMS 24h before appointment | Allied health, professional services |
| `scheduling/new-booking-welcome-email.json` | Calendly booking webhook | Send welcome email | All |
| `notifications/web-form-to-email-slack.json` | Webhook (web form POST) | Email + Slack notification | All |
| `notifications/google-sheets-row-to-slack.json` | Google Sheets — new row | Slack notification | All |
| `outreach/apollo-qualified-leads-to-neo-claude.json` | Cron (weekdays) | Personalize + draft + send cold outreach + update sheet | Internal outbound |
| `allied-health/new-patient-welcome-sequence.json` | Webhook / Splose | Welcome email sequence | Allied health |
| `allied-health/recall-reminder.json` | Cron (weekly) | Email/SMS recall reminder | Allied health |

## Exporting a workflow as a template

1. Open the workflow in n8n
2. Click the three-dot menu → **"Download"**
3. Save the JSON to the appropriate subdirectory with a descriptive kebab-case filename
4. Open the JSON and replace any real client data (email addresses, phone numbers, business names, API endpoint URLs) with obvious placeholders like `YOUR_EMAIL_HERE`, `YOUR_XERO_ACCOUNT_ID`, etc.
5. Commit with message: `feat(n8n): add [workflow name] template`

> **Note on credentials:** n8n strips credential secrets automatically on export — you do not need to redact API keys or tokens from the JSON. However, step 4 still applies: business-specific values embedded in node configuration (email addresses, phone numbers, webhook URLs, account IDs) are **not** stripped automatically and must be replaced with placeholders manually before committing.

## Client isolation

All client workflows live in the same n8n workspace (n8n Projects is an enterprise-only feature). Organisation is via **tags and naming conventions**.

**Workflow naming:** `[Client] — [Category] — [Trigger] → [Action]`

Examples:
```
RelayAI Internal — Notifications — Webhook → Email + Slack
Acme Physio — Scheduling — Cron → Appointment Reminder
XYZ Trades — Accounting — Xero Invoice Overdue → Email
```

**Tags:** Create one tag per client slug (e.g. `acme-physio`, `relayai-internal`). Apply it to every workflow for that client so you can filter by client in the n8n dashboard.

**Credentials:** Name credentials `[Client] — [Integration]` (e.g. `Acme Physio — Xero OAuth`, `Acme Physio — HubSpot`). This prevents accidentally using one client's credentials in another client's workflow.

## n8n instance

Production: https://n8n.relayai.com.au (admin credentials in password manager — clients never access this directly)
Version: n8n v1.x (self-hosted)
