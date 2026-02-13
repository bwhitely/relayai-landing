# WhatsApp Setup Guide (Twilio Sandbox)

## Prerequisites
- Twilio account (free trial works)
- ngrok installed (`~/.local/bin/ngrok`)
- Agent service running locally (`uvicorn app.main:app --reload`)

## Step 1: Start ngrok tunnel

```bash
~/.local/bin/ngrok http 8000
```

Copy the HTTPS forwarding URL (e.g. `https://abc123.ngrok-free.app`).

## Step 2: Configure Twilio Sandbox

1. Go to [Twilio Console > Messaging > Try it out > Send a WhatsApp message](https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn)
2. Follow the instructions to join the sandbox (send "join <word-word>" to the sandbox number)
3. Go to **Sandbox Settings** (or [direct link](https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox))
4. Set **"When a message comes in"** to:
   ```
   https://YOUR-NGROK-URL/webhooks/twilio/whatsapp
   ```
5. Set HTTP method to **POST**
6. Save

## Step 3: Update your .env

Update these values in `agent-service/.env` with your real Twilio credentials:

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
```

Find these at [Twilio Console > Account Info](https://console.twilio.com/).

## Step 4: Update the tenant

The tenant needs a `twilio_phone_number` matching the Twilio sandbox number
(usually `+14155238886`):

```bash
curl -X PUT "http://localhost:8000/admin/tenants/YOUR_TENANT_ID" \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"twilio_phone_number": "+14155238886"}'
```

## Step 5: Test

Send a WhatsApp message to the sandbox number from your phone. You should
get an AI response back.

## Troubleshooting

- **403 "Invalid Twilio signature"**: Make sure your ngrok URL in the Twilio
  sandbox config exactly matches what's running. Twilio signs requests using
  the webhook URL.
- **404 "No tenant for this number"**: The `twilio_phone_number` on your
  tenant must match the `To` number in the webhook (the sandbox number,
  without the `whatsapp:` prefix).
- **Restart uvicorn** after changing `.env` values — `--reload` only picks
  up code changes, not env file changes.
