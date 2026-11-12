# Snugs Free Baby Stuff Weekly Subscribe Worker

Cloudflare Worker handling double opt-in email subscriptions for the Snugs "Free Baby Stuff Weekly" list using Resend.

## Bot Protection Note

Turnstile omitted; honeypot only (`website` field on `POST /subscribe`).

## Routes

- `POST /subscribe` - JSON `{ "email": "...", "website": "" }`. Validates the email, ignores bot submissions where `website` is non-empty, checks the global Resend contact and segment membership, and sends a 48-hour HMAC-signed confirmation link.
- `GET /confirm?token=...` - Non-mutating confirmation landing page in Snugs styling. Renders a "Confirm my email" form button (with CSRF field) for valid tokens, "You're already on the list" if already confirmed in the segment, or an expired/invalid notice linking back to `https://snugs.ai/free-baby-stuff/`.
- `POST /confirm` - Requires same-origin (`Origin` or `Referer` matching `SITE_ORIGIN` or the Worker host) and a valid token. Flips the global Resend contact to `unsubscribed: false` once, ensures membership in the `RESEND_AUDIENCE_ID` segment, sends a single welcome email, and renders "You're on the list". Reloading or re-posting renders "You're already on the list" without sending another welcome email.
- All other paths/methods return `404`.

## Configuration & Secrets

Non-secret configuration lives in `wrangler.toml` under `[vars]`:

- `RESEND_AUDIENCE_ID`: ID of the `Free Baby Stuff Weekly` segment in Resend (contacts are global in Resend and membership is via the Resend segment whose id is `RESEND_AUDIENCE_ID`; placeholder `""` in repo, set by Pete before deploy).
- `SITE_ORIGIN`: `"https://snugs.ai"`
- `FROM_EMAIL`: `"Snugs <hello@snugs.ai>"`

Secrets are never stored in the repository. Set them via Wrangler before previewing or deploying:

```bash
cd workers/free-baby-stuff
wrangler secret put RESEND_API_KEY
wrangler secret put TOKEN_SECRET
# Optional if Turnstile is added in the future:
# wrangler secret put TURNSTILE_SECRET
```

## Local Tests & Preview

Run the unit test suite (uses `node --test` with mocked `fetch`, no network or API key required):

```bash
cd workers/free-baby-stuff
npm test
```

Run a local or preview Worker (`workers_dev = true` is enabled in `wrangler.toml`, with no production routes attached):

```bash
cd workers/free-baby-stuff
wrangler dev
# Or deploy to the *.workers.dev preview subdomain:
wrangler deploy
```

## Attaching Production Routes (After Go-Live Approval)

Do not attach production routes on `snugs.ai` until Claudiu gives the go-live approval on issue #29.

Once approved, Pete can attach the Worker routes on the `snugs.ai` Cloudflare zone either in the Cloudflare Dashboard (Workers Routes -> add routes for `snugs.ai/subscribe` and `snugs.ai/confirm*` pointing to `snugs-free-baby-stuff`) or by adding the zone route entries to `wrangler.toml` and running `wrangler deploy`.
