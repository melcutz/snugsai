#!/usr/bin/env python3
"""Verify SEO batch 1 (issue #19): wake-window tool, month schedules,
regression hub, nap-transition checker, tools hub + free-tools blocks.

Checks (all must pass; exit non-zero on any failure):
  1.  Every new page file exists.
  2.  <title> present, <= 60 chars, unique across the whole site.
  3.  <meta name="description"> present and unique among the new pages.
  4.  Exactly one <h1> per new page.
  5.  First <p> after the H1 is the 40-60 word answer paragraph.
  6.  Self-referencing canonical https://snugs.ai/<path>/ (exact).
  7.  JSON-LD parses and contains the required types:
        tools  -> SoftwareApplication + FAQPage + BreadcrumbList
        content-> Article + FAQPage + BreadcrumbList
        tools hub -> FAQPage + BreadcrumbList + CollectionPage
        (hub ruling: a link hub is not an application, so no
         SoftwareApplication on /tools/ itself)
  8.  Trial CTA: app.snugs.ai anchor(s) with utm_source=snugs.ai,
      utm_medium=seo, utm_campaign=<page slug>; cta_click + link_domain
      binder present; sticky mobile CTA on leaf pages (before the binder),
      no sticky on the tools hub (verify_sticky_mobile_cta.py rule).
  9.  Every site-absolute internal href on a new page resolves to an
      existing file (directory hrefs resolve to <dir>/index.html).
 10.  sitemap.xml parses as XML and contains every new URL with lastmod.
 11.  Month pages link previous month, next month, their regression page
      and both tools.
 12.  Every new page cites AAP / CDC / NSF, carries the "not medical
      advice" note and the dad-reviewer box.
 13.  No orphan pages: every new URL has at least one inbound internal
      link from the site's HTML.
 14.  index.html and resources/index.html carry the free-tools block
      markers and link the tools.
"""

import html
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://snugs.ai"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

MONTHS = list(range(13, 37))
SCHEDULE_SLUGS = [f"{m}-month-old-schedule" for m in MONTHS]
REGRESSION_SLUGS = [
    "4-month-sleep-regression",
    "8-month-sleep-regression",
    "12-month-sleep-regression",
    "18-month-sleep-regression",
    "2-year-sleep-regression",
]

# new page file -> kind (tool | hub | content)
NEW_PAGES: dict[str, str] = {
    "tools/index.html": "hub",
    "tools/wake-window-calculator/index.html": "tool",
    "tools/nap-transition-checker/index.html": "tool",
    "schedules/index.html": "content",
    "sleep-regressions/index.html": "content",
}
for _s in SCHEDULE_SLUGS:
    NEW_PAGES[f"schedules/{_s}/index.html"] = "content"
for _s in REGRESSION_SLUGS:
    NEW_PAGES[f"sleep-regressions/{_s}/index.html"] = "content"

# leaf pages get the sticky mobile CTA; the three hubs follow the
# verify_sticky_mobile_cta.py "article pages only" rule (no sticky).
LEAF_PAGES = [
    p for p in NEW_PAGES
    if p not in ("tools/index.html", "schedules/index.html", "sleep-regressions/index.html")
]

REQUIRED_TYPES = {
    "tool": {"SoftwareApplication", "FAQPage", "BreadcrumbList"},
    "content": {"Article", "FAQPage", "BreadcrumbList"},
    "hub": {"FAQPage", "BreadcrumbList", "CollectionPage"},
}

# month -> regression page a month page must link (proximity of onset)
def regression_for(month: int) -> str:
    if month <= 15:
        return "12-month-sleep-regression"
    if month <= 23:
        return "18-month-sleep-regression"
    return "2-year-sleep-regression"


def url_path(page: str) -> str:
    """Page file -> site URL path with trailing slash."""
    return page[: -len("index.html")] if page.endswith("index.html") else page


def slug_for(page: str) -> str:
    return Path(page).parent.name if page.endswith("index.html") else Path(page).stem


def strip_tags(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment))


errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


# ---------------------------------------------------------------- 1. exists
files: dict[str, str] = {}
for page in NEW_PAGES:
    path = ROOT / page
    if not path.exists():
        fail(f"1 MISSING PAGE {page}")
    else:
        files[page] = path.read_text(encoding="utf-8")

# ------------------------------------------------- 2/3/4 titles + desc + h1
titles: dict[str, str] = {}
for p in ROOT.rglob("*.html"):
    if ".git" in p.parts:
        continue
    text = p.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"<title>(.*?)</title>", text, re.S)
    if m:
        titles[str(p.relative_to(ROOT))] = html.unescape(m.group(1)).strip()
title_values: dict[str, list[str]] = {}
for rel, t in titles.items():
    title_values.setdefault(t, []).append(rel)

for page, text in files.items():
    t = titles.get(page)
    if not t:
        fail(f"2 NO TITLE {page}")
        continue
    if len(t) > 60:
        fail(f"2 TITLE TOO LONG ({len(t)}) {page}: {t}")
    if len(title_values[t]) > 1:
        fail(f"2 TITLE NOT UNIQUE {page}: {t} also in {title_values[t]}")
    m = re.search(r'<meta name="description" content="([^"]*)"', text)
    if not m or not m.group(1).strip():
        fail(f"3 NO META DESCRIPTION {page}")

descs: dict[str, list[str]] = {}
for page, text in files.items():
    m = re.search(r'<meta name="description" content="([^"]*)"', text)
    if m:
        descs.setdefault(m.group(1), []).append(page)
for d, pages in descs.items():
    if len(pages) > 1:
        fail(f"3 META DESCRIPTION NOT UNIQUE: {pages}")

for page, text in files.items():
    h1s = re.findall(r"<h1[\s>]", text)
    if len(h1s) != 1:
        fail(f"4 H1 COUNT {len(h1s)} (want 1) {page}")

# ------------------------------------------------- 5. answer paragraph 40-60
for page, text in files.items():
    h1 = re.search(r"</h1>", text)
    if not h1:
        continue  # already flagged by h1 count
    m = re.search(r"<p[^>]*>(.*?)</p>", text[h1.end():], re.S)
    if not m:
        fail(f"5 NO ANSWER PARAGRAPH {page}")
        continue
    words = strip_tags(m.group(1)).split()
    if not (40 <= len(words) <= 60):
        fail(f"5 ANSWER WORDS {len(words)} (want 40-60) {page}")

# ------------------------------------------------------------- 6. canonical
for page, text in files.items():
    want = f'<link rel="canonical" href="{SITE}/{url_path(page)}" />'
    m = re.search(r'<link rel="canonical" href="([^"]*)"', text)
    if not m:
        fail(f"6 NO CANONICAL {page}")
    elif m.group(1) != f"{SITE}/{url_path(page)}":
        fail(f"6 CANONICAL NOT SELF {page}: {m.group(1)} != {SITE}/{url_path(page)}")

# ------------------------------------------------------------- 7. JSON-LD
for page, text in files.items():
    kind = NEW_PAGES[page]
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', text, re.S
    )
    types: set[str] = set()
    ok = True
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError as e:
            fail(f"7 JSON-LD PARSE {page}: {e}")
            ok = False
            continue
        nodes = data.get("@graph", [data]) if isinstance(data, dict) else [data]
        for n in nodes:
            if isinstance(n, dict):
                t = n.get("@type")
                if isinstance(t, list):
                    types.update(t)
                elif t:
                    types.add(t)
    if not ok:
        continue
    missing = REQUIRED_TYPES[kind] - types
    if missing:
        fail(f"7 JSON-LD MISSING {sorted(missing)} {page} (has {sorted(types)})")

# ------------------------------------------------------------- 8. CTA + UTM
def cta_links(text: str) -> list[str]:
    out = []
    for m in re.finditer(r"<a\b[^>]*>", text):
        tag = m.group(0)
        if "data-cta" in tag:
            hm = re.search(r'href="([^"]*)"', tag)
            if hm:
                out.append(html.unescape(hm.group(1)))
    return out


for page, text in files.items():
    slug = slug_for(page)
    hrefs = cta_links(text)
    app = [h for h in hrefs if "app.snugs.ai" in h]
    if not app:
        fail(f"8 NO app.snugs.ai CTA {page}")
    for h in app:
        checks = {
            "utm_source": "snugs.ai",
            "utm_medium": "seo",
            "utm_campaign": slug,
        }
        for k, v in checks.items():
            if not re.search(rf"[?&]{k}={re.escape(v)}(&|\"|$)", h):
                fail(f"8 CTA UTM {page}: {h} missing {k}={v}")
    if "cta_click" not in text or "link_domain" not in text:
        fail(f"8 cta_click/link_domain binder missing {page}")
    if "querySelectorAll('[data-cta]')" not in text and 'querySelectorAll("[data-cta]")' not in text:
        fail(f"8 data-cta binder script missing {page}")
    sticky = 'data-cta="sticky_mobile"' in text
    if page in LEAF_PAGES:
        if not sticky:
            fail(f"8 STICKY CTA MISSING {page}")
        else:
            if text.find('data-cta="sticky_mobile"') > text.find("querySelectorAll('[data-cta]')"):
                fail(f"8 STICKY AFTER BINDER {page}")
            if "snugs-sticky-cta" not in text:
                fail(f"8 STICKY CSS MISSING {page}")
            if ".snugs-sticky-dismiss" not in text:
                fail(f"8 STICKY DISMISS MISSING {page}")
    elif sticky:
        # hub pages follow verify_sticky_mobile_cta.py "article pages only"
        fail(f"8 HUB MUST NOT HAVE STICKY {page}")

# ------------------------------------------------- 9. internal links resolve
def resolve(href: str) -> Path | None:
    path = href.split("#", 1)[0].split("?", 1)[0]
    if path == "/":
        return ROOT / "index.html"
    rel = path.lstrip("/")
    target = ROOT / rel
    if rel.endswith("/"):
        target = target / "index.html"
    return target


for page, text in files.items():
    for href in re.findall(r'href="(/[^"]*)"', text):
        if href.startswith("//"):
            continue
        target = resolve(href)
        if target is None or not target.exists():
            fail(f"9 BROKEN INTERNAL LINK {page} -> {href}")

# ------------------------------------------------------------ 10. sitemap
new_urls = [f"{SITE}/{url_path(p)}" for p in NEW_PAGES]
try:
    tree = ElementTree.parse(ROOT / "sitemap.xml")
    locs = {
        (e.find("s:loc", NS).text or "").strip(): (e.find("s:lastmod", NS).text or "").strip()
        if e.find("s:lastmod", NS) is not None
        else ""
        for e in tree.getroot().findall("s:url", NS)
        if e.find("s:loc", NS) is not None
    }
except Exception as e:  # noqa: BLE001
    fail(f"10 SITEMAP XML INVALID: {e}")
    locs = {}
for u in new_urls:
    if u not in locs:
        fail(f"10 URL MISSING FROM SITEMAP {u}")
    elif not locs[u]:
        fail(f"10 URL MISSING LASTMOD {u}")

# ------------------------------------------------- 11. month page cross-links
for m in MONTHS:
    page = f"schedules/{m}-month-old-schedule/index.html"
    text = files.get(page, "")
    want = []
    if m > 13:
        want.append(f"/schedules/{m - 1}-month-old-schedule/")
    if m < 36:
        want.append(f"/schedules/{m + 1}-month-old-schedule/")
    want.append(f"/sleep-regressions/{regression_for(m)}/")
    want.append("/tools/wake-window-calculator/")
    want.append("/tools/nap-transition-checker/")
    for w in want:
        if f'href="{w}"' not in text:
            fail(f"11 MONTH LINK MISSING {page} -> {w}")

# ------------------------------------------- 12. citations + note + dad box
for page, text in files.items():
    low = text.lower()
    if "american academy of pediatrics" not in low and "aap" not in low:
        fail(f"12 AAP CITATION MISSING {page}")
    if "cdc" not in low:
        fail(f"12 CDC CITATION MISSING {page}")
    if "national sleep foundation" not in low and "nsf" not in low:
        fail(f"12 NSF CITATION MISSING {page}")
    if "not medical advice" not in low:
        fail(f"12 NOT-MEDICAL-ADVICE NOTE MISSING {page}")
    if "Written by a dad" not in text or "From the founder of Snugs.ai" not in text:
        fail(f"12 DAD REVIEWER BOX MISSING {page}")

# ------------------------------------------------------------ 13. orphans
all_hrefs: set[str] = set()
for p in ROOT.rglob("*.html"):
    if ".git" in p.parts:
        continue
    t = p.read_text(encoding="utf-8", errors="ignore")
    for href in re.findall(r'href="(/[^"]*)"', t):
        path = href.split("#", 1)[0].split("?", 1)[0]
        if path and not path.endswith("/index.html"):
            all_hrefs.add(path)
        elif path.endswith("/index.html"):
            all_hrefs.add(path[: -len("index.html")])
for page in NEW_PAGES:
    up = f"/{url_path(page)}"  # all_hrefs entries keep their leading slash
    if up == "/index.html":
        continue
    if up not in all_hrefs:
        fail(f"13 ORPHAN PAGE (no inbound link) {page}")

# --------------------------------------------------- 14. free-tools blocks
for page in ("index.html", "resources/index.html"):
    text = (ROOT / page).read_text(encoding="utf-8", errors="ignore")
    if "<!-- free-tools:start -->" not in text or "<!-- free-tools:end -->" not in text:
        fail(f"14 FREE-TOOLS MARKERS MISSING {page}")
    else:
        start = text.index("<!-- free-tools:start -->")
        end = text.index("<!-- free-tools:end -->")
        block = text[start:end]
        for want in ("/tools/", "/tools/wake-window-calculator/", "/tools/nap-transition-checker/"):
            if f'href="{want}"' not in block:
                fail(f"14 FREE-TOOLS BLOCK MISSING LINK {page} -> {want}")

# ------------------------------------------------------------------ report
print(f"New pages checked : {len(NEW_PAGES)} ({len(LEAF_PAGES)} leaf)")
print(f"Sitemap new URLs  : {len(new_urls)}")
print(f"Failures          : {len(errors)}")
for e in errors:
    print(" -", e)
if errors:
    sys.exit(1)
print("\nOK: batch 1 checks passed.")
