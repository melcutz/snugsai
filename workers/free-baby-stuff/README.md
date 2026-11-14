# Snugs Free Baby Stuff Weekly Subscribe Worker

Cloudflare Worker handling double opt-in email subscriptions for the Snugs "Free Baby Stuff Weekly" list using Resend.

## Bot Protection Note

Turnstile omitted; honeypot only (`website` field on `POST /subscribe`).

## Routes

- `POST /subscribe` - JSON `{ "email": "...", "website": "" }`. Validates the email, ignores bot submissions where `website` is non-empty, checks the global Resend contact and segment membership, and sends a 48-hour HMAC-signed confirmation link.
- `GET /confirm?token=...` - Non-mutating confirmation landing page in Snugs styling. Renders a "Confirm my email" form button (with CSRF field) for valid tokens, "You're already on the list" if already confirmed in the segment, or an expired/invalid notice linking back to `https://snugs.ai/free-baby-stuff/`.
- `POST /confirm` - Requires same-origin (`Origin` or `Referer` matching `SITE_ORIGIN` or the Worker host) and a valid token. Flips the global Resend contact to `unsubscribed: false` once, ensures membership in the `RESEND_AUDIENCE_ID` segment, sends a single welcome email, and renders "You're on the list". Reloading or re-posting renders "You're already on the list" without sending another welcome email.
- `GET /unsubscribe?token=...` - Read-only unsubscribe landing page (makes no Resend API calls). Validates the AES-GCM encrypted unsubscribe token and renders a `POST /unsubscribe` confirmation form, or a `400` invalid-link page.
- `POST /unsubscribe` - Accepts the encrypted unsubscribe token via query string or `token` form field (supports RFC 8058 one-click `List-Unsubscribe=One-Click` POSTs without `Origin`/`Referer`/CSRF). Removes the contact from the `RESEND_AUDIENCE_ID` segment and sets `unsubscribed: true` only when no other segments remain on the contact.
- Transactional confirmation and welcome emails include a signed/encrypted `${SITE_ORIGIN}/unsubscribe?token=...` link along with `List-Unsubscribe` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` headers.
- All other paths/methods return `404`.

## Configuration & Secrets

Worker observability is enabled in `wrangler.toml` (`[observability]` with `enabled = true`), and upstream errors are logged with sanitized messages that redact emails, tokens, and API keys.

Non-secret configuration lives in `wrangler.toml` under `[vars]`:

- `RESEND_AUDIENCE_ID`: ID of the `Free Baby Stuff Weekly` segment in Resend (contacts are global in Resend and membership is via the Resend segment whose id is `RESEND_AUDIENCE_ID`; placeholder `""` in repo, set by Pete before deploy).
- `SITE_ORIGIN`: `"https://snugs.ai"`
- `FROM_EMAIL`: `"Snugs <hello@snugs.ai>"`

Secrets are never stored in the repository. Set them via Wrangler before previewing or deploying (names only, never commit values):

```bash
cd workers/free-baby-stuff
# Preview / default environment:
wrangler secret put RESEND_API_KEY
wrangler secret put TOKEN_SECRET

# Production environment (--env production):
wrangler secret put RESEND_API_KEY --env production
wrangler secret put TOKEN_SECRET --env production
# Optional if Turnstile is added in the future:
# wrangler secret put TURNSTILE_SECRET --env production
```

## Local Tests & Preview

Run the unit test suite (uses `node --test` with mocked `fetch`, no network or API key required):

```bash
cd workers/free-baby-stuff
npm test
```

Run a local or preview Worker (`workers_dev = true` is enabled at the top level of `wrangler.toml`, with no production routes attached):

```bash
cd workers/free-baby-stuff
wrangler dev
# Or deploy to the *.workers.dev preview subdomain:
wrangler deploy
```

## Production Deploy & Rollback (After Go-Live Approval)

Do not deploy to production on `snugs.ai` until Claudiu gives explicit go-live approval.

The `[env.production]` block in `wrangler.toml` sets `workers_dev = false`, enables observability, sets `SITE_ORIGIN = "https://snugs.ai"`, and attaches the `snugs.ai` zone routes (`snugs.ai/subscribe`, `snugs.ai/confirm*`, `snugs.ai/unsubscribe*`).

### Production Deploy Steps

1. Ensure `RESEND_AUDIENCE_ID` in `[env.production.vars]` is set to the production Resend segment ID.
2. Ensure required secrets (`RESEND_API_KEY` and `TOKEN_SECRET`) are configured for `--env production`:
   ```bash
   cd workers/free-baby-stuff
   wrangler secret put RESEND_API_KEY --env production
   wrangler secret put TOKEN_SECRET --env production
   ```
3. Deploy the production environment:
   ```bash
   cd workers/free-baby-stuff
   wrangler deploy --env production
   ```

### Rollback Steps

To roll back a production deployment to the previous working version:

```bash
cd workers/free-baby-stuff
wrangler deployments list --env production
wrangler rollback --env production
```
