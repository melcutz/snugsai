# SEO prune / consolidate (issue #8)

Google Search Console showed 56 of 482 pages indexed with 407 "Crawled -
currently not indexed". Off-audience pages (dating profiles, adult supplement
comparisons, gifts for a daughter's boyfriend, teen topics) were getting the
impressions, while core toddler queries (e.g. 18-month sleep regression)
ranked 43-86. `sitemap.xml` also needed rebuilding around the pages worth
indexing. No page used `noindex` before this change.

## Classification rules (`scripts/seo_classify.py` → `classification.csv`)

Every `resources/*.html` is read (title, h1, meta description) and given one
of `keep / merge / noindex / remove`:

- **keep** – pregnancy, newborn, baby and toddler (~0-3) topics, plus general
  dad/parent topics that clearly serve parents of young kids.
- **noindex** – off-audience: dating profiles and adult romance, adult
  supplements/product comparisons, teens/tweens/school-age-only topics,
  adult children and in-laws of grown kids, novelty/non-parenting topics.
- **merge** – near-duplicate articles on the same core topic. The strongest
  article is kept as `merge_target`; the rest become redirect stubs.
- **remove** – empty/broken pages only. Conservative: prefer `noindex`.

Check order matters (see script for the exact regexes):

1. `remove` if the title is missing or the file is tiny.
2. `merge` if the slug is in the curated `MERGE_GROUPS` table.
3. Explicitly off-audience patterns (dating, teens, adult supplements, …)
   are checked **before** the allowlist, because those pages often also
   mention "father"/"single parent".
4. A core 0-3 allowlist (sleep training/regressions, lullabies, swaddling,
   contact naps, baby poop, potty training, tantrums, postpartum, …) forces
   `keep`. All matches use regex word boundaries, so "between" never matches
   "tween" and "protein" never matches "teen".
5. Conservative default: `keep`.

Current counts: **keep 386, noindex 54, merge 29, remove 0** (469 articles).

After changing the rules, re-run and fix edge cases in `classification.csv`
by hand: no `noindex` row may contain core 0-3 terms in its title, every
`merge_target` must exist and be `keep`.

## Applying decisions

- `scripts/apply_decisions.py` – adds
  `<meta name="robots" content="noindex, follow">` to every `noindex` page
  and replaces every `merge` page with a minimal stub (canonical to the
  target, `noindex`, meta refresh, visible link). GitHub Pages cannot do
  server-side 301s, so the stub is the interim redirect. Also writes
  `seo/redirects-301.csv` (`from,to` full URLs).
- `scripts/build_sitemap.py` – regenerates `sitemap.xml` with the top-level
  pages (`/`, `/resources/`, contact, privacy, terms,
  `/tools/sleep-milestone-calculator.html`) plus every `keep` article, with
  `lastmod` from `git log`. `noindex`/`merge`/`remove` pages are excluded.
  `robots.txt` already references `https://snugs.ai/sitemap.xml`.
- `scripts/enrich_core30.py` – enriches the ~30 strongest 0-3 articles in
  `seo/core30.txt`: 3–5 contextual internal links to other keep articles, a
  short "Written by a dad" author box (Claudiu Branzan, founder of Snugs.ai
  and dad of a toddler), and Article-schema JSON-LD (author as Person,
  datePublished/dateModified from git history, publisher Snugs.ai).
- `scripts/verify_seo.py` – parses every HTML file, checks sitemap URLs
  resolve to indexable files, no `noindex` page is in the sitemap, redirect
  targets exist and are `keep`, and core-30 JSON-LD is valid.

Regenerate after content changes with:

```sh
python3 scripts/seo_classify.py   # review classification.csv edge cases
python3 scripts/build_sitemap.py
python3 scripts/verify_seo.py
```

## Post-merge manual steps

1. In Google Search Console: submit `https://snugs.ai/sitemap.xml` and use
   URL Inspection → "Request indexing" for each URL in `seo/core30.txt`.
2. Once the site is proxied through Cloudflare: add Bulk Redirects from
   `seo/redirects-301.csv` (real 301s `from` → `to`), then the stub pages
   can stay as a fallback.
3. Keep `classification.csv` as the source of truth when adding new
   articles: classify first, then decide index vs noindex before publishing.
