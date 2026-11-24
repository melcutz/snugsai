# Notes: Site Polish (Issue #33)

This document tracks before and after states for the site polish items on the marketing site (`snugs.ai`), notes on deferred items, and references for the follow-up app repository tasks.

---

## 1. Favicon and Touch Icons

- Status: Fixed
- Before:
  - Every page pointed `rel="icon"` to `/og/snugs-og.jpg`, a 1200x630 OpenGraph JPEG image.
  - `favicon.svg` existed in the repository root but was not linked from any page.
  - Direct browser requests for `/favicon.ico` returned HTTP 404.
  - No Apple Touch Icon was provided or linked.
- After:
  - Generated a clean 32x32 `favicon.ico` from existing repository logo assets (`og/icon-512.png`).
  - Generated a standard 180x180 `apple-touch-icon.png` from existing repository logo assets (`og/icon-512.png`).
  - Updated all 479 HTML pages to point `rel="icon"` to `/favicon.svg` with `type="image/svg+xml"`.
  - Added `<link rel="apple-touch-icon" href="/apple-touch-icon.png">` across all 479 HTML pages.
  - Updated generator scripts and templates (`scripts/batch1_pages.py`, `scripts/build_schedules.py`, `scripts/generate_hubs.py`, `scripts/hub_template.html`) so newly generated pages maintain the correct favicon and touch icon tags.
  - Existing `og:image` and `twitter:image` tags continue to reference `/og/snugs-og.jpg` for social sharing previews.

---

## 2. Broken Wake-Window Calculator Internal Links

- Status: Fixed
- Before:
  - Links to `/tools/wake-window-calculator.html` returned HTTP 404 because the tool is served from the directory route `/tools/wake-window-calculator/`.
  - Four resource guides linked to the broken `.html` path:
    - `resources/4-month-sleep-regression-survival-guide.html`
    - `resources/huckleberry-alternative.html`
    - `resources/smart-sleep-coach-closing-what-to-use-next.html`
    - `resources/snoo-vs-cradlewise-smart-bassinet-comparison.html`
- After:
  - Corrected all four occurrences to link to `/tools/wake-window-calculator/`.
  - Created an automated sitemap crawler and link validation script (`scripts/check_internal_links.py`).
  - Created automated test suite (`tests/test_site_polish.mjs`) executing under the Node test runner to crawl all 169 sitemap URLs and verify that 100 percent of internal links resolve to existing files or directories.
  - Verified that zero internal 404 links remain across all sitemap pages.

---

## 3. Tailwind CDN

- Status: Skipped (Documented Rationale)
- Rationale:
  - 479 static HTML files currently load the Tailwind CDN script (`cdn.tailwindcss.com`) and configure custom themes via per-page inline `<script>tailwind.config = {...}</script>` blocks.
  - The marketing site repository does not currently contain a Node/npm package manifest (`package.json`), CSS build step, or checked-in CSS bundle.
  - Setting up a standalone PostCSS/Tailwind build pipeline to compile a unified CSS bundle across 479 distinct static pages with heterogeneous inline configurations is a major redesign that carries significant risk of breaking layouts or dropping page-specific styles.
  - Per the issue instructions ("If it would be a large risky redesign, skip it and record the reason in NOTES-33.md rather than breaking layouts"), the Tailwind CDN approach is preserved at this stage to ensure layout stability.

---

## 4. CTA and Parameter Preservation

- Status: Verified Preserved
- All CTA anchors pointing to `https://app.snugs.ai/` retain required parameters:
  - `utm_source=marketing_site`
  - `utm_medium=cta`
  - `utm_campaign=<slug>`
  - `plan=monthly` and `plan=yearly` on pricing CTAs
- Verified with `python3 scripts/verify_cta_utm.py` (0 failures across all 929 checked CTAs).

---

## 5. Companion Repository Changes (app.snugs.ai)

Tasks for the application repository (`snugs-ai`) are documented in detail in:
- `APP-SNUGS-AI-CHANGES.md`

Key items for `app.snugs.ai`:
- Meta description and OpenGraph tags in `index.html` (description, og:title, og:description, og:image, twitter:card).
- Fix duplicate `<link rel="manifest">` tags in `index.html`.
- Deploy `public/robots.txt` disallowing search engine indexing of private app routes.
- Implement unknown-path 404 behavior for static asset misses and invalid SPA routes.
- Ensure inbound CTA UTM and plan parameters are preserved through application routing and onboarding flows.
