# Outreach Workflow Template

Template file: `apollo-qualified-leads-to-neo-claude.json`

## What this workflow does

1. Runs on a weekday schedule (daily)
2. Reads `Leads` from Google Sheets
3. Filters to leads eligible for outreach (`new` / `retry`, has email, not unsubscribed/replied/bounced)
4. Caps the batch to `DAILY_OUTREACH_LIMIT` (default 20)
5. Pulls basic website content for personalization
6. Generates personalized outreach with Claude API
7. Appends compliant signature + unsubscribe URL
8. Creates a draft marker in workflow data (Resend has no transactional draft endpoint)
9. Sends the email via Resend API
10. Updates lead row status/timestamps in Google Sheets

## Required credentials in n8n

- Google Sheets OAuth2
- HTTP Bearer Auth credential named `Resend` (for Resend API)
- Anthropic API key (via env var `ANTHROPIC_API_KEY`)

## Required environment variables

- `ANTHROPIC_API_KEY`
- `UNSUBSCRIBE_BASE_URL` (example: `https://getrelayai.com.au/unsubscribe`)
- `RESEND_FROM_EMAIL` (optional, default: `ben@getrelayai.com.au`)
- `DAILY_OUTREACH_LIMIT` (optional, default: `20`)
- `MIN_DAYS_BETWEEN_TOUCHES` (optional, default: `7`)

## Google Sheet setup

Create a sheet named `Leads` and use columns from `google-sheet-schema.csv`.
At minimum, this workflow expects:

- `lead_id`
- `email`
- `status`
- `first_name`
- `company`
- `domain` (or inferable from email)
- `next_send_at`
- `last_contacted_at`
- `unsubscribed`
- `bounced`
- `replied`

## Resend draft note

Resend transactional email API (`/emails`) sends directly and does not provide a true per-email draft endpoint.
This workflow uses a `Create Draft (Resend Marker)` code node to represent draft-ready state before send.

## Recommended companion workflows

1. Reply listener: marks `replied=true`, `status=responded`, and stops future sends.
2. Unsubscribe webhook: marks `unsubscribed=true`, `status=unsubscribed`.
3. Bounce handler: marks `bounced=true`, `status=bounced` and suppresses future sends.

## Import

1. n8n -> Add Workflow -> Import from file
2. Select `apollo-qualified-leads-to-neo-claude.json`
3. Reconnect credentials
4. Replace `YOUR_GOOGLE_SHEET_ID`
5. Run once manually before activation
