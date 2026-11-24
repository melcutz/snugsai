# Brief: app.snugs.ai Configuration and Metadata Updates

This brief outlines exact, file-level updates to apply in the companion repository (`snugs-ai`) for `app.snugs.ai`.

## Scope

1. Meta and OpenGraph tags in `index.html`
2. Removal of duplicate web app manifest link in `index.html`
3. `public/robots.txt` configuration
4. Unknown-path 404 routing behavior
5. Preservation of inbound CTA UTM and plan query parameters

---

## 1. Meta and OpenGraph Tags (`index.html`)

In `index.html`, add or update the following standard metadata and social card tags inside the `<head>` element:

```html
<!-- Primary Meta Tags -->
<meta name="description" content="Your 24/7 AI parenting expert. Live AI that reads baby cries and cues on camera with sleep coaching and milestone tracking.">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="website">
<meta property="og:url" content="https://app.snugs.ai/">
<meta property="og:title" content="Snugs - Your 24/7 AI Parenting Expert">
<meta property="og:description" content="Live AI that reads baby cries and cues on camera. Works on iPhone, Android or desktop with no app install required.">
<meta property="og:image" content="https://snugs.ai/og/snugs-og.jpg">

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:url" content="https://app.snugs.ai/">
<meta name="twitter:title" content="Snugs - Your 24/7 AI Parenting Expert">
<meta name="twitter:description" content="Live AI that reads baby cries and cues on camera. Works on iPhone, Android or desktop with no app install required.">
<meta name="twitter:image" content="https://snugs.ai/og/snugs-og.jpg">
```

---

## 2. Duplicate Manifest Fix (`index.html`)

Inspect `<head>` in `index.html` for multiple `<link rel="manifest" ...>` tags.

Ensure only one manifest link is present:

```html
<link rel="manifest" href="/manifest.json">
```

Remove any redundant second `<link rel="manifest" ...>` tag.

---

## 3. Robots Configuration (`public/robots.txt`)

Ensure `public/robots.txt` exists with the following configuration to prevent search engine indexing of authenticated app sessions and private application routes:

```txt
User-agent: *
Disallow: /
```

If public marketing/landing pages exist on the app host, disallow internal and authenticated paths (such as `/api/`, `/auth/`, `/app/`, `/settings/`) while allowing public routes. For a pure client app, disallowing all paths is standard.

---

## 4. Unknown-Path 404 Behavior

Ensure unknown paths that do not match static assets or defined application routes return or display a clear 404 state:

1. Static asset misses (e.g. `/assets/nonexistent.js` or `/images/missing.png`) must return an HTTP 404 status code rather than falling back to `index.html`.
2. For single-page app routing (Cloudflare Pages or SPA host), configure a designated catch-all route (`*`) in the client router that renders a user-friendly Not Found screen with a button to return to the application home (`/`).
3. If using Cloudflare Pages static routing, ensure a `public/404.html` is provided so non-SPA requests receive an explicit 404 page.

---

## 5. CTA Parameter Preservation (UTM and Plan)

Inbound traffic from the marketing site (`snugs.ai`) directs users to `app.snugs.ai` with campaign and plan parameters.

Common query parameters include:
- `utm_source=marketing_site`
- `utm_medium=cta`
- `utm_campaign=<campaign_name>` (e.g. `wake-window-calculator`, `home-hero`, `4-month-sleep-regression-survival-guide`)
- `plan=monthly` or `plan=yearly` (from pricing cards)

Requirements:
- Client-side routing, initial authentication redirects, and onboarding screens must preserve these query parameters in the URL or capture them into session storage upon initial landing.
- Do not strip `utm_*` or `plan` parameters during redirect loops or route transitions before sign-up completion.
