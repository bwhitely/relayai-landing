# Client Onboarding Guide

Step-by-step process for onboarding a new client onto the RelayAI platform.

---

## Phase 1: Discovery (Before Signing)

### 1. Initial Contact

- Client reaches out via landing page form, referral, or cold outreach
- Respond within 24 hours
- Schedule a 30-minute discovery call

### 2. Discovery Call

Run through the [Discovery Interview Questions](templates/discovery-questions.md). Key things to establish:

- What does the business do? What industry?
- What channels do customers currently use to reach them? (phone, email, web form, WhatsApp, social)
- What's their biggest pain point? (missed calls, after-hours enquiries, repetitive admin, booking no-shows)
- What systems do they already use? (CRM, booking system, accounting, spreadsheets)
- How many inbound enquiries per week/month?
- Who handles enquiries now, and how long does it take?
- What does their ideal response look like?

### 3. Scoping

Based on discovery, determine:

| Decision | Options |
|----------|---------|
| **Channel** | WhatsApp, SMS, web chat widget, or any combination |
| **CRM integration** | HubSpot (general), Splose (allied health), Google Sheets (simple/budget), or none |
| **Calendar integration** | Google Calendar (general), Calendly (self-service booking), Splose (allied health via CRM), or none |
| **Accounting integration** | Xero (invoicing/payments), or none |
| **Escalation channels** | Slack, email, both, or neither |
| **Tools needed** | create_lead, search_contacts, check_availability, book_appointment, escalate_to_human, send_email, search_invoices, check_payment_status |
| **Tier** | Starter (100 convos/mo), Growth (500), Custom |

### 4. Proposal & Contract

- Use the [Service Agreement template](templates/service-agreement.md)
- Use the [Statement of Work template](templates/statement-of-work.md)
- Send via email, get signed (DocuSign or similar)
- Collect first month's payment

---

## Phase 2: Setup (Days 1-3)

### 5. Create Tenant

Via the admin dashboard (`/admin/dashboard`) or API:

```bash
curl -X POST http://localhost:8000/admin/tenants \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Client Business Name",
    "max_conversations_per_month": 100,
    "crm_type": "hubspot",
    "crm_credentials": "their-hubspot-api-key",
    "calendar_type": "google_calendar",
    "calendar_credentials": "{\"client_email\": \"...\", \"private_key\": \"...\", \"calendar_id\": \"...\"}",
    "accounting_type": "xero",
    "accounting_credentials": "{\"client_id\": \"...\", \"client_secret\": \"...\", \"refresh_token\": \"...\", \"xero_tenant_id\": \"...\", \"access_token\": \"...\", \"token_expiry\": \"...\"}",
    "escalation_config": {
      "slack_webhook_url": "https://hooks.slack.com/services/...",
      "email": "owner@business.com"
    },
    "system_prompt": "...",
    "tools_config": {"enabled": ["create_lead", "search_contacts", "check_availability", "book_appointment", "escalate_to_human", "send_email", "search_invoices", "check_payment_status"]}
  }'
```

All credential fields (`crm_credentials`, `calendar_credentials`, `accounting_credentials`, `twilio_auth_token`) are encrypted at rest automatically.

### 6. Write the System Prompt

This is the most important step. The system prompt defines the agent's personality, knowledge, and behaviour. Template:

```
You are a friendly and professional receptionist for [BUSINESS NAME] in [LOCATION].

About the business:
- [What they do]
- [Services offered]
- [Operating hours]
- [Address]

Your responsibilities:
- Greet customers warmly
- Answer common questions about services, pricing, and availability
- Collect customer contact details (name, email, phone) and save them using the create_lead tool
- If a customer wants to book, use check_availability to find open times, then book_appointment to confirm
- After booking, send a confirmation email using send_email
- If a customer asks about an invoice or payment, use search_invoices or check_payment_status
- If you cannot help or the customer asks to speak to someone, use escalate_to_human

Important rules:
- Never make up information you don't know — offer to have someone follow up instead
- Keep responses concise and conversational (2-3 sentences max)
- Be warm but professional
- Always set an appropriate lead_status when creating leads (NEW for first contact, OPEN if they're actively engaged)
```

Tailor this heavily based on the discovery call. The more specific, the better.

### 7. Set Up CRM Integration

**HubSpot:**
1. Client creates a free HubSpot account (https://app.hubspot.com/signup-hubspot/crm)
2. Settings > Integrations > Private Apps > Create
3. Scopes: `crm.objects.contacts.read`, `crm.objects.contacts.write`
4. Copy the access token
5. Set as `crm_credentials` on the tenant

**Splose (allied health):**
1. Client provides API key from their Splose workspace (Settings > API)
2. Get their default practitioner ID, service ID, and location ID
3. Set as `crm_credentials`:
   ```json
   {
     "api_key": "...",
     "default_practitioner_id": 1,
     "default_service_id": 1,
     "default_location_id": 1
   }
   ```

**Google Sheets (budget/simple):**
1. Create a Google Sheet with headers: First Name, Last Name, Email, Phone, Company, Notes
2. Share with the service account email
3. Set credentials with sheet ID

### 8. Set Up Calendar Integration (if applicable)

Calendar is configured separately from CRM, so a client can use e.g. HubSpot for contacts + Google Calendar for bookings.

**Google Calendar:**
1. Create a Google Cloud project (or use the existing RelayAI project)
2. Enable the Google Calendar API in the Cloud Console
3. Create a service account (IAM & Admin > Service Accounts > Create)
4. Create a JSON key for the service account and download it
5. The client shares their Google Calendar with the service account email address (the `client_email` from the key file) — give it "Make changes to events" permission
6. Set `calendar_type` to `google_calendar` on the tenant
7. Set `calendar_credentials` with the required fields:
   ```json
   {
     "client_email": "relay@your-project.iam.gserviceaccount.com",
     "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
     "calendar_id": "client@gmail.com"
   }
   ```
   - `client_email`: From the service account JSON key
   - `private_key`: From the service account JSON key (keep the `\n` formatting)
   - `calendar_id`: The client's calendar email address, or `"primary"` if using the service account's own calendar

**Calendly:**
1. Client creates a Calendly account (free or paid) at https://calendly.com
2. Client generates a Personal Access Token: https://calendly.com/integrations/api_webhooks — click "Get a token"
3. Get the Event Type URI — either from the Calendly API or from the Calendly dashboard URL:
   - Dashboard URL looks like `https://calendly.com/username/30min`
   - The API event type URI looks like `https://api.calendly.com/event_types/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`
   - To get it programmatically: `curl -H "Authorization: Bearer TOKEN" https://api.calendly.com/event_types?user=https://api.calendly.com/users/USERID`
4. Set `calendar_type` to `calendly` on the tenant
5. Set `calendar_credentials`:
   ```json
   {
     "api_key": "their-calendly-personal-access-token",
     "event_type_uri": "https://api.calendly.com/event_types/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
   }
   ```

> **Note:** Calendly doesn't support direct booking via API for external users. When the agent calls `book_appointment` with a Calendly tenant, it returns the public scheduling link instead. The agent will share this link with the customer so they can self-book. `check_availability` works normally and returns available time slots.

**Splose (allied health):**
Calendar is handled automatically when `crm_type` is `splose` — no separate calendar config needed. The `check_availability` and `book_appointment` tools will use the Splose availability and appointments APIs via the CRM credentials.

**No calendar:**
If the client doesn't need booking, set `calendar_type` to `none` and don't enable the `check_availability` or `book_appointment` tools.

### 9. Set Up Escalation Notifications (Slack + Email)

Escalation notifications are configured via the `escalation_config` JSONB field on the tenant. You can configure Slack, email, or both. When the agent calls `escalate_to_human`, it will send notifications to all configured channels.

**Slack:**
1. Create a Slack Incoming Webhook in the client's workspace (or your own for monitoring):
   - Go to https://api.slack.com/apps — Create New App > From Scratch
   - Select the client's workspace (or yours)
   - Features > Incoming Webhooks > Activate
   - "Add New Webhook to Workspace" > select a channel (e.g. #escalations)
   - Copy the webhook URL
2. Add to `escalation_config`:
   ```json
   {
     "slack_webhook_url": "https://hooks.slack.com/services/T.../B.../xxx"
   }
   ```

> **Who creates the Slack app?** Typically you create ONE Slack app in your own workspace, then add webhooks for different channels per client. If the client wants notifications in their own Slack, they create the app in their workspace and give you the webhook URL.

**Email (via Resend):**
1. You need a Resend account with a verified sending domain (one-time setup — see `.env` section below)
2. Add the client's notification email to `escalation_config`:
   ```json
   {
     "email": "owner@clientbusiness.com"
   }
   ```
3. If the client wants to use their own Resend account (optional), add their API key:
   ```json
   {
     "email": "owner@clientbusiness.com",
     "resend_api_key": "re_their_key",
     "from_email": "agent@clientbusiness.com"
   }
   ```

**Both (recommended):**
```json
{
  "slack_webhook_url": "https://hooks.slack.com/services/T.../B.../xxx",
  "email": "owner@clientbusiness.com"
}
```

If one channel fails (e.g. Slack is down), the other still delivers. The agent response includes which channels were notified.

### 10. Set Up Accounting Integration (if applicable)

**Xero:**

Xero uses OAuth2, which is more involved than API key auth. You'll need to register a Xero app once.

**One-time setup (your Xero developer account):**
1. Go to https://developer.xero.com/app/manage — log in or sign up
2. Create a new app:
   - App name: "RelayAI Agent"
   - Company URL: your domain
   - OAuth 2.0 redirect URI: `https://yourdomain.com/oauth/xero/callback` (you'll need this for token exchange)
3. Copy the **Client ID** and **Client Secret**

**Per-client setup:**
1. The client authorises your Xero app to access their organisation:
   - Direct them to: `https://login.xero.com/identity/connect/authorize?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&scope=openid profile email accounting.transactions.read offline_access&state=CLIENT_TENANT_ID`
   - They log in and authorise
   - You receive a code at your redirect URI
   - Exchange the code for tokens:
     ```bash
     curl -X POST https://identity.xero.com/connect/token \
       -H "Content-Type: application/x-www-form-urlencoded" \
       -d "grant_type=authorization_code&code=THE_CODE&redirect_uri=YOUR_REDIRECT_URI&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET"
     ```
   - Response contains `access_token`, `refresh_token`, `expires_in`
2. Get the client's Xero Tenant ID (organisation ID):
   ```bash
   curl -H "Authorization: Bearer ACCESS_TOKEN" https://api.xero.com/connections
   ```
   Returns an array — use the `tenantId` from the client's organisation.
3. Set `accounting_type` to `xero` on the tenant
4. Set `accounting_credentials`:
   ```json
   {
     "client_id": "your-xero-app-client-id",
     "client_secret": "your-xero-app-client-secret",
     "refresh_token": "from-oauth-exchange",
     "access_token": "from-oauth-exchange",
     "token_expiry": "2024-01-15T10:00:00+00:00",
     "xero_tenant_id": "from-connections-api"
   }
   ```

> **Token refresh is automatic.** When the access token expires (every 30 minutes), the agent service refreshes it using the refresh token and saves the updated credentials back to the tenant record. You don't need to manually refresh tokens.

> **Scopes:** The current integration uses `accounting.transactions.read` (search/view invoices). If you later need to create invoices, add `accounting.transactions` to the OAuth scope.

### 11. Set Up WhatsApp (if applicable)

1. Client needs a Twilio account (or use your master account)
2. For testing: use Twilio WhatsApp sandbox
3. For production: apply for a Twilio WhatsApp Business number
4. Set `twilio_phone_number`, `twilio_account_sid`, `twilio_auth_token` on the tenant
5. Configure Twilio webhook URL to: `https://yourdomain.com/webhooks/twilio/whatsapp`

### 12. Set Up SMS (if applicable)

SMS uses the same Twilio infrastructure as WhatsApp. A single phone number can handle both WhatsApp and SMS — Twilio routes to different webhook URLs based on the channel.

1. Buy a Twilio phone number with SMS capability (or use the same number as WhatsApp)
2. Set `twilio_phone_number` on the tenant to the E.164 number (e.g. `+61412345678`)
3. Set `twilio_account_sid` and `twilio_auth_token` on the tenant (or use fallback from `.env`)
4. In the Twilio console for that phone number:
   - Under **Messaging > A MESSAGE COMES IN**, set the webhook to: `https://yourdomain.com/webhooks/twilio/sms`
   - Method: HTTP POST
5. If the same number is also used for WhatsApp, configure the WhatsApp webhook separately in the Twilio WhatsApp sandbox/sender settings

> **Same number, both channels:** Twilio keeps WhatsApp and SMS webhooks separate. You can point WhatsApp to `/webhooks/twilio/whatsapp` and SMS to `/webhooks/twilio/sms` on the same phone number. Conversations are tracked separately per channel.

### 13. Deploy Chat Widget (if applicable)

See [Widget Integration Guide](widget-integration.md) for full details.

Quick version — give the client this snippet for their website:

```html
<script
  src="https://yourdomain.com/static/widget.js"
  data-relay-tenant="TENANT_API_KEY"
  data-relay-url="https://yourdomain.com">
</script>
```

---

## Your .env Setup

These are server-level settings that you configure once in your `.env` file. They are NOT per-client.

```bash
# Required
DATABASE_URL=postgresql+asyncpg://agents:localdev@localhost:5432/agents
ANTHROPIC_API_KEY=sk-ant-xxxxx          # Your Anthropic API key (pays for all LLM usage)
ADMIN_API_KEY=change-me-to-a-random-string
FERNET_KEY=generate-with-python-cryptography-fernet  # For encrypting tenant credentials at rest

# Twilio (fallback — used when tenant doesn't have their own Twilio creds)
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx

# Email via Resend (shared across all tenants unless overridden per-tenant)
RESEND_API_KEY=re_xxxxx                 # Get from https://resend.com/api-keys
DEFAULT_FROM_EMAIL=noreply@relayai.com.au  # Must match a verified domain in Resend

# Optional
DEFAULT_MODEL=claude-sonnet-4-5-20250514
MAX_AGENT_ITERATIONS=5
AGENT_TIMEOUT_SECONDS=30
LOG_LEVEL=INFO
```

### What you need accounts for

| Service | Who creates the account | Per-client or shared? | What you need |
|---------|------------------------|----------------------|---------------|
| **Anthropic** | You | Shared — one API key for all tenants | API key in `.env` |
| **Twilio** | You (or per-client) | Shared fallback + per-client override | Account SID + Auth Token in `.env`; client's own SID/token optional on tenant |
| **Resend** | You | Shared — one API key for all tenants | API key in `.env`; must verify your sending domain in Resend dashboard |
| **Slack** | You (or client) | Per-client — each tenant gets their own webhook URL | Client creates app or you add webhooks per channel |
| **HubSpot** | Client | Per-client | Client creates a Private App, gives you the token |
| **Google Calendar** | You (service account) | Shared service account, per-client calendar sharing | One service account; each client shares their calendar with it |
| **Calendly** | Client | Per-client | Client creates Personal Access Token, gives you that + event type URI |
| **Splose** | Client | Per-client | Client creates API key in Splose settings |
| **Xero** | You (developer app) + Client (authorises) | Shared app, per-client OAuth authorisation | You register ONE Xero app; each client goes through OAuth flow |

---

## Phase 3: Testing (Days 3-5)

### 14. Internal Testing

- Send test messages through the configured channels (WhatsApp, SMS, web widget)
- Verify leads appear in the CRM with correct fields and lead status
- If calendar is configured: test check_availability returns busy/free periods, and book_appointment creates events on the calendar (or returns a Calendly link)
- If escalation is configured: trigger an escalation and verify Slack message / email arrives
- If email is configured: test send_email delivers to the recipient
- If Xero is configured: test search_invoices and check_payment_status return real data
- Test edge cases: no name given, rude messages, requests to speak to a human, out-of-scope questions
- Check the admin dashboard Usage and Conversations tabs

### 15. Client Testing

- Walk the client through sending test messages
- Show them leads appearing in their CRM
- If calendar is configured: show them test bookings appearing on their Google Calendar, Calendly, or Splose
- Show them escalation notifications arriving in Slack / email
- Get feedback on tone, responses, and any missing info
- Iterate on the system prompt based on feedback (usually 2-3 rounds)

---

## Phase 4: Go Live (Day 5-7)

### 16. Launch

- Switch from sandbox to production WhatsApp / SMS number (if applicable)
- Deploy widget on client's live website
- Set `is_active = true` (should already be)
- Monitor the first 24-48 hours closely via admin dashboard

### 17. Handover

- Send the client a summary email:
  - What's been set up (channels, CRM, calendar, escalation, accounting)
  - How to check their CRM for new leads
  - If calendar is configured: how bookings will appear on their calendar
  - If Slack is configured: which channel to watch for escalations
  - Who to contact if something goes wrong
  - When their first bill is

---

## Phase 5: Ongoing

### 18. Monthly Check-in

- Review usage stats in admin dashboard
- Check for any failed conversations or escalations
- Adjust system prompt if the business has changed
- If using Xero: verify OAuth tokens are still refreshing (check logs for refresh errors)
- Invoice for the month

### 19. Common Issues

| Issue | Solution |
|-------|----------|
| Agent gives wrong info | Update the system prompt with correct facts |
| Too many escalations | Add more info to the system prompt so the agent can handle more |
| CRM not receiving leads | Check CRM credentials haven't expired, test with a direct API call |
| Calendar not showing bookings | Check the client has shared their calendar with the service account email and granted "Make changes to events" permission |
| Calendly shows no availability | Verify the `event_type_uri` is correct; check the event type is active in Calendly |
| Google Calendar auth failing | Service account key may have expired — regenerate in Cloud Console and update `calendar_credentials` |
| Xero token refresh failing | Client may have revoked access — re-run the OAuth flow to get new tokens |
| Xero "forbidden" errors | Check the OAuth scope includes `accounting.transactions.read`; check the `xero_tenant_id` is correct |
| Slack notifications not arriving | Test the webhook URL directly: `curl -X POST -H "Content-Type: application/json" -d '{"text":"test"}' WEBHOOK_URL` |
| Email not sending | Check `RESEND_API_KEY` is set in `.env`; verify sending domain in Resend dashboard |
| Email going to spam | Set up SPF/DKIM/DMARC for your sending domain in Resend |
| WhatsApp not responding | Check Twilio webhook URL, check ngrok/tunnel is running, check logs |
| SMS not responding | Check Twilio SMS webhook URL is set to `/webhooks/twilio/sms` (not the WhatsApp URL) |
| Widget not loading | Check CORS settings, verify the script src URL is correct |

---

## Quick Reference: All Integrations

| Integration | Config Field | Credential Field | Auth Type |
|-------------|-------------|-----------------|-----------|
| HubSpot | `crm_type: "hubspot"` | `crm_credentials` (API key string) | API key |
| Google Sheets | `crm_type: "google_sheets"` | `crm_credentials` (JSON with sheet_id) | Service account |
| Splose | `crm_type: "splose"` | `crm_credentials` (JSON with api_key) | API key |
| Google Calendar | `calendar_type: "google_calendar"` | `calendar_credentials` (JSON) | Service account |
| Calendly | `calendar_type: "calendly"` | `calendar_credentials` (JSON) | Personal Access Token |
| Xero | `accounting_type: "xero"` | `accounting_credentials` (JSON) | OAuth2 |
| Slack | `escalation_config.slack_webhook_url` | In escalation_config | Incoming Webhook |
| Email (Resend) | `escalation_config.email` | `RESEND_API_KEY` in .env (or per-tenant override) | API key |
| WhatsApp | `twilio_phone_number` | `twilio_account_sid` + `twilio_auth_token` | API key |
| SMS | `twilio_phone_number` | `twilio_account_sid` + `twilio_auth_token` | API key |

## Available Tools (10 total)

| Tool | Purpose | Requires |
|------|---------|----------|
| `echo` | Testing only | Nothing |
| `create_lead` | Save customer contact details | CRM integration |
| `update_lead` | Update existing contact | CRM integration (not Google Sheets) |
| `search_contacts` | Check if customer exists | CRM integration |
| `check_availability` | Find open booking slots | Calendar or Splose integration |
| `book_appointment` | Book an appointment | Calendar or Splose integration |
| `escalate_to_human` | Notify business owner | Slack and/or Email config (works without, just logs) |
| `send_email` | Send email to customer | Resend API key (in .env or per-tenant) |
| `search_invoices` | Search invoices by customer/status | Xero integration |
| `check_payment_status` | Get invoice payment details | Xero integration |
