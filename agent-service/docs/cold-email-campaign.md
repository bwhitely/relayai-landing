# Cold Email Campaign Plan for RelayAI

## Context

Outbound cold email to generate leads for RelayAI's automation services, targeting Australian SMBs. Covers: prospect list building, email infrastructure, tooling, legal compliance, and campaign execution.

---

## 1. Australian Spam Act Compliance (CRITICAL)

The Australian Spam Act 2003 applies. Cold email to businesses is **legal** in Australia provided you follow these rules:

- **Identify yourself clearly** — every email must include your business name, ABN, and contact details
- **Include an unsubscribe mechanism** — functional, honoured within 5 business days
- **No misleading subject lines** — must accurately represent the content
- **B2B exemption** — you CAN email business addresses without prior consent, as long as the message is relevant to their business role
- **Don't scrape personal emails** — only email addresses published in a business context (company website, LinkedIn, business directory)

**Bottom line:** Cold emailing Australian businesses at their work email is legal. Just include your ABN, a real reply address, and an unsubscribe link.

---

## 2. Email Infrastructure — DO NOT Use ben@relayai.com.au

Using your primary domain for cold outreach is risky. If recipients mark emails as spam, your `relayai.com.au` domain reputation tanks — meaning regular emails (client comms, transactional, form submissions) start landing in spam too.

### Recommended setup:

| Purpose | Domain | Email |
|---------|--------|-------|
| Main business | relayai.com.au | ben@relayai.com.au |
| Cold outreach | **getrelayai.com.au** or **tryrelayai.com.au** | ben@getrelayai.com.au |

### Steps:

1. Register a secondary `.com.au` domain (~$15/year)
2. Set up DNS records: SPF, DKIM, DMARC (all essential for deliverability)
3. Set up a simple redirect so the domain points to `relayai.com.au`
4. **Warm the domain for 2-3 weeks** before sending campaigns — send normal emails from it first to build reputation
5. Use Google Workspace or Zoho Mail for the mailbox (~$7-10/month)

---

## 3. Cold Email Sending Tools

**Don't use Resend, Mailchimp, or SendGrid for cold email** — they're for opted-in lists and will ban your account.

### Recommended tools (designed for cold outreach):

| Tool | Price | Notes |
|------|-------|-------|
| **Instantly.ai** | ~$30/month | Best for beginners. Built-in warmup, sequences, analytics. |
| **Smartlead** | ~$39/month | Similar to Instantly, good deliverability features |
| **Lemlist** | ~$59/month | More features, image personalisation, LinkedIn steps |

**Recommendation: Instantly.ai** — cheapest, simplest, built-in domain warmup, handles sending limits automatically (ramps from 10/day to 50+/day over 2-3 weeks).

These tools all:
- Connect to your outreach mailbox via IMAP/SMTP
- Handle automatic warmup
- Send as if from your regular email client (no bulk-send headers)
- Track opens, replies, bounces
- Auto-stop sequences when someone replies
- Handle unsubscribe links

---

## 4. Building Your Prospect List

### Who to target:

1. **Allied health clinics** (physio, chiro, psychology, OT) — strongest vertical with Splose integration
2. **Trades businesses** with 5-20 employees — big enough for admin pain, too small for IT staff
3. **Real estate agencies** — constant enquiry volume, appointment scheduling
4. **Professional services** (accounting firms, law firms, bookkeepers)
5. **Hospitality** — booking, roster, supplier management

### How to find prospects:

**Option A: Manual (free, slow, highest quality)**
- Google Maps: search "[industry] Adelaide", "[industry] South Australia"
- Grab business name, website, phone, email from their listing or website
- Hunter.io (free: 25 searches/month) to find email addresses from domains
- LinkedIn Sales Navigator ($99/month) to find owners by role + location + industry

**Option B: Lead databases (paid, fast)**

| Tool | Price | Notes |
|------|-------|-------|
| **Apollo.io** | Free (10k records) | Best free option. Filter by industry, location, company size, job title. Has AU businesses. |
| **Hunter.io** | Free 25/month, $49/month for 500 | Domain search + email finder |
| **UpLead** | $99/month | Verified emails, good AU coverage |
| **LinkedIn Sales Navigator** | $99/month | Best for finding decision-makers. Export with Evaboot or PhantomBuster. |

**Recommendation:** Start with **Apollo.io** (free tier). Filter:
- Location: Australia (or Adelaide / South Australia for local)
- Company size: 2-50 employees
- Industry: Healthcare, Construction, Real Estate, Professional Services
- Job title: Owner, Founder, Director, Practice Manager, Office Manager

### List hygiene:

- **Verify every email before sending** — use ZeroBounce, NeverBounce, or Instantly's built-in verification
- Aim for <2% bounce rate
- Remove generic addresses (info@, admin@, reception@) — target named individuals

---

## 5. Campaign Structure

### Email sequence (3-4 emails over 2 weeks):

**Email 1 (Day 0) — The opener**
- Short (60-80 words), plain text, no images or HTML
- Reference something specific about their business
- One clear pain point relevant to their industry
- Soft CTA: "Would it be worth a quick chat?"

**Email 2 (Day 3) — The value add**
- Follow up on email 1
- Share a specific insight or link to a relevant blog post
- Same soft CTA

**Email 3 (Day 7) — Social proof**
- Brief example of a result (your demo tenant works — "we built an AI agent for a physio clinic that handles booking enquiries 24/7")
- Quantify: "responds in under 10 seconds", "handles enquiries outside business hours"

**Email 4 (Day 12) — The breakup**
- Short: "I'll assume the timing isn't right. No worries — if automation comes up, happy to chat."
- Creates urgency without being pushy — often gets the highest reply rate

### Example opener (allied health):

```
Subject: Quick question about [Clinic Name]

Hi [First Name],

I noticed [Clinic Name] is running on Splose — are you finding
that enquiry handling and booking management is eating into your
admin time?

We build automation for allied health clinics in Adelaide — things
like WhatsApp booking agents, automatic appointment reminders, and
CRM sync that runs in the background.

Would it be worth a 15-minute chat to see if any of that would
save you time?

Ben
RelayAI | Business Automation
relayai.com.au
ABN: 46 873 536 821
Unsubscribe: [link]
```

---

## 6. Metrics to Track

| Metric | Good | Problem |
|--------|------|---------|
| Open rate | 40-60% | Below 30% = deliverability issue |
| Reply rate | 3-8% | Below 2% = copy needs work |
| Bounce rate | <2% | Above 3% = list quality issue |
| Positive reply rate | 1-3% | = meetings booked |

---

## 7. Execution Timeline

| Week | Action |
|------|--------|
| 1 | Register outreach domain, set up DNS (SPF/DKIM/DMARC), create mailbox, connect to Instantly, start warmup |
| 2-3 | Domain warming (Instantly handles automatically). Meanwhile: build prospect list in Apollo, write email sequences, verify emails |
| 4 | Start sending — 20-30 emails/day |
| 5+ | Ramp to 50/day, analyse results, iterate on copy |

---

## 8. Budget Summary

| Item | Cost | Frequency |
|------|------|-----------|
| Outreach domain (.com.au) | ~$15 | Yearly |
| Google Workspace mailbox | ~$10 | Monthly |
| Instantly.ai | ~$30 | Monthly |
| Apollo.io | Free | — |
| Email verification | ~$10 per 1,000 | Per batch |
| **Total to start** | **~$65** | **Month 1** |

---

## Quick-Start Checklist

- [ ] Register `getrelayai.com.au` (or similar)
- [ ] Set up Google Workspace mailbox on the new domain
- [ ] Configure SPF, DKIM, DMARC DNS records
- [ ] Sign up for Instantly.ai, connect mailbox, start warmup
- [ ] Sign up for Apollo.io (free), build first prospect list (allied health Adelaide)
- [ ] Write 4-email sequence for allied health vertical
- [ ] Verify email list (ZeroBounce or Instantly built-in)
- [ ] After 2-3 weeks warmup: launch first campaign at 20-30/day
- [ ] Track metrics weekly, iterate on copy
