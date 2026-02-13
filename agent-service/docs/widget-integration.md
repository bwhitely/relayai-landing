# Widget Integration Guide

How to deploy the RelayAI chat widget on a client's website.

---

## Overview

The widget is a single JavaScript file (`/static/widget.js`) served by the agent service. It renders a floating chat button in the bottom-right corner of the page. When clicked, it opens a chat window that communicates with the agent via the generic webhook endpoint.

No framework, no build step, no dependencies. One `<script>` tag.

---

## Basic Installation

Add this snippet just before `</body>` on the client's website:

```html
<script
  src="https://your-relay-domain.com/static/widget.js"
  data-relay-tenant="TENANT_API_KEY_HERE"
  data-relay-url="https://your-relay-domain.com">
</script>
```

| Attribute | Required | Description |
|-----------|----------|-------------|
| `src` | Yes | URL to the widget JS file on your server |
| `data-relay-tenant` | Yes | The tenant's API key (from admin dashboard) |
| `data-relay-url` | Yes | Base URL of the agent service (no trailing slash) |

### Where to find the tenant API key

1. Log into the admin dashboard (`/admin/dashboard`)
2. Click on the tenant
3. Copy the API key from the detail page

---

## Platform-Specific Instructions

### WordPress

1. Install the "Insert Headers and Footers" plugin (or use theme's custom code area)
2. Go to Settings > Insert Headers and Footers
3. Paste the script snippet in the "Scripts in Footer" box
4. Save

Alternatively, edit `footer.php` in the theme and add the snippet before `</body>`.

### Squarespace

1. Go to Settings > Advanced > Code Injection
2. Paste the snippet in the "Footer" section
3. Save

### Wix

1. Go to Settings > Custom Code
2. Click "Add Custom Code"
3. Paste the snippet
4. Set placement to "Body - end"
5. Apply to "All pages"

### Shopify

1. Go to Online Store > Themes > Edit Code
2. Open `theme.liquid`
3. Paste the snippet just before `</body>`
4. Save

### Static HTML / Custom Site

Just add the `<script>` tag before `</body>` in the HTML.

### React / Angular / Vue (SPA)

Add the script tag to `index.html` (not inside a component). The widget manages its own lifecycle and doesn't conflict with framework routing.

For React (`public/index.html`):
```html
<script
  src="https://your-relay-domain.com/static/widget.js"
  data-relay-tenant="TENANT_API_KEY"
  data-relay-url="https://your-relay-domain.com">
</script>
</body>
```

---

## How It Works (for your reference)

1. Widget JS loads and creates a floating button (bottom-right corner)
2. User clicks the button, chat window opens
3. User types a message
4. Widget sends `POST /webhooks/generic/{tenant_id}` with:
   - `sender_id`: a randomly generated session ID (stored in `sessionStorage`)
   - `message`: the user's text
   - `X-API-Key` header: the tenant API key from `data-relay-tenant`
5. Agent processes the message, returns a response
6. Widget displays the response in the chat window
7. Conversation continues with full history (server-side, keyed by sender_id)

---

## Customisation

The widget uses its own shadow DOM and internal styles, so it won't conflict with the client's CSS. Currently, visual customisation is limited to what's built into the widget.

If a client needs custom branding (colours, logo, position), you'd need to modify `widget.js` directly or add data attributes for those options. This is a future enhancement.

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Widget doesn't appear | Script not loading | Check browser console for 404s. Verify the `src` URL is correct and the server is running |
| "Failed to send" error | CORS or network issue | Ensure the agent service has CORS allowing the client's domain. Check `data-relay-url` is correct |
| Widget appears but no response | Tenant inactive or wrong API key | Verify the API key matches, check tenant is active in admin dashboard |
| Widget loads on some pages but not others | Script only added to certain templates | Make sure the snippet is in a global footer/template, not a single page |
| Chat history lost on page navigation | Expected for SPAs doing full reloads | `sender_id` is in `sessionStorage`, so history persists within the same tab session. Server-side conversation history persists regardless |

---

## CORS

The agent service is configured with `allow_origins=["*"]` by default. If you lock this down in production, make sure to add the client's domain:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://clientdomain.com.au"],
    ...
)
```

---

## Security Notes

- The tenant API key is visible in the page source. This is intentional — it only grants access to send messages to that tenant's agent via the generic webhook. It cannot access admin endpoints, other tenants, or any sensitive data.
- Rate limiting is applied on the webhook endpoint to prevent abuse.
- The `sender_id` is client-generated. Don't use it for authentication or identity — it's just for conversation threading.
