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

## Template index

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
| `allied-health/new-patient-welcome-sequence.json` | Webhook / Splose | Welcome email sequence | Allied health |
| `allied-health/recall-reminder.json` | Cron (weekly) | Email/SMS recall reminder | Allied health |

## Exporting a workflow as a template

1. Open the workflow in n8n
2. Click the three-dot menu → **"Download"**
3. Save the JSON to the appropriate subdirectory with a descriptive kebab-case filename
4. Open the JSON and replace any real client data (email addresses, phone numbers, business names, API endpoint URLs) with obvious placeholders like `YOUR_EMAIL_HERE`, `YOUR_XERO_ACCOUNT_ID`, etc.
5. Commit with message: `feat(n8n): add [workflow name] template`

> **Note on credentials:** When a credential node appears in an exported workflow, n8n replaces the actual secret with a reference ID. On import into a new instance, n8n will prompt you to reconnect — this is expected. You do not need to manually redact credentials from the JSON export.

## Client isolation

Each client's workflows live in their own n8n **Project** named `Client — [Business Name]`.
Credentials configured inside a Project are not visible to other Projects.

Naming convention for workflows within a project:
```
[Category] — [Trigger] → [Action]

Examples:
  Xero — Invoice Overdue → Email Reminder
  Calendly — New Booking → HubSpot Contact
  Forms — Typeform Submission → Slack Notification
```

## n8n instance

Production: https://n8n.relayai.com.au (admin credentials in password manager — clients never access this directly)
