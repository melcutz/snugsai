#!/usr/bin/env python3
"""Verify the SEO prune/consolidate work for issue #8.

Checks:
  1. Every HTML file still parses (html.parser).
  2. Every sitemap URL maps to an existing file that is not noindex.
  3. No noindex page is in the sitemap.
  4. Every redirect target exists and is a keep page.
  5. The JSON-LD on the core 30 is valid JSON with an Article node.
Prints the decision counts and sitemap URL count. Exits non-zero on failure.
"""

import csv
import json
import re
import sys
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

BASE = Path(__file__).resolve().parent.parent
SITE = "https://snugs.ai"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
errors = []


class ParseCheck(HTMLParser):
    def error(self, message):
        raise ValueError(message)


def check_parses(path: Path):
    try:
        ParseCheck().feed(path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"PARSE FAIL {path}: {e}")


def main():
    rows = list(csv.DictReader(open(BASE / "seo" / "classification.csv")))
    by_path = {r["path"]: r for r in rows}
    counts = Counter(r["decision"] for r in rows)

    # 1. every HTML file parses (resources + top-level + tools)
    html_files = (
        list((BASE / "resources").glob("*.html"))
        + [BASE / f for f in ("index.html", "contact.html", "privacy.html", "terms.html")]
        + list((BASE / "tools").glob("*.html"))
    )
    for f in html_files:
        check_parses(f)
    print(f"1. parsed {len(html_files)} HTML files OK")

    # decisions present on disk
    for r in rows:
        p = BASE / r["path"]
        if not p.exists():
            errors.append(f"MISSING FILE {r['path']}")
            continue
        html = p.read_text(encoding="utf-8")
        if r["decision"] == "noindex" and "noindex" not in html:
            errors.append(f"NOINDEX TAG MISSING {r['path']}")
        if r["decision"] == "merge":
            for token in ("noindex", 'http-equiv="refresh"', 'rel="canonical"'):
                if token not in html:
                    errors.append(f"MERGE STUB MISSING {token} {r['path']}")

    # 2+3. sitemap checks
    tree = ElementTree.parse(BASE / "sitemap.xml")
    locs = [e.text.strip() for e in tree.getroot().findall("s:url/s:loc", NS)]
    assert locs, "sitemap has no URLs"
    for loc in locs:
        assert loc.startswith(SITE + "/"), f"sitemap URL off-site: {loc}"
        rel = loc[len(SITE) + 1:] or "index.html"
        if rel in ("", "/"):
            rel = "index.html"
        target = BASE / rel
        if rel == "resources/":
            if not (target / "index.html").exists():
                errors.append("SITEMAP resources/ index missing")
            continue
        if not target.exists():
            errors.append(f"SITEMAP DANGLING {loc}")
            continue
        dec = by_path.get(rel)
        if dec and dec["decision"] in ("noindex", "merge", "remove"):
            errors.append(f"SITEMAP HAS {dec['decision'].upper()} PAGE {loc}")
    noindexed = {r["path"] for r in rows if r["decision"] == "noindex"}
    for n in noindexed:
        if f"{SITE}/{n}" in locs:
            errors.append(f"NOINDEX PAGE IN SITEMAP {n}")
    print(f"2/3. {len(locs)} sitemap URLs map to existing indexable files OK")

    # 4. redirect targets
    r301 = list(csv.DictReader(open(BASE / "seo" / "redirects-301.csv")))
    for row in r301:
        for col in ("from", "to"):
            assert row[col].startswith(SITE + "/resources/"), row
        to_rel = row["to"][len(SITE) + 1:]
        from_rel = row["from"][len(SITE) + 1:]
        if not (BASE / to_rel).exists():
            errors.append(f"REDIRECT TARGET MISSING {row['to']}")
        elif by_path.get(to_rel, {}).get("decision") != "keep":
            errors.append(f"REDIRECT TARGET NOT KEEP {row['to']}")
        if by_path.get(from_rel, {}).get("decision") != "merge":
            errors.append(f"REDIRECT SOURCE NOT MERGE {row['from']}")
    print(f"4. {len(r301)} redirect targets exist and are keep OK")

    # 5. core-30 JSON-LD valid + Article node + author/links present
    core = [l.strip() for l in open(BASE / "seo" / "core30.txt") if l.strip()]
    assert len(core) == 30, f"core30 has {len(core)} lines"
    n_links = 0
    for c in core:
        html = (BASE / c).read_text(encoding="utf-8")
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        if not m:
            errors.append(f"NO JSON-LD {c}")
            continue
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            errors.append(f"JSON-LD INVALID {c}: {e}")
            continue
        nodes = data.get("@graph", [data])
        article = next((n for n in nodes if n.get("@type") == "Article"), None)
        if article is None:
            errors.append(f"NO ARTICLE NODE {c}")
        elif article.get("author", {}).get("@type") != "Organization":
            errors.append(f"AUTHOR NOT ORGANIZATION {c}")
        if "Claudiu Branzan" in html or "Claudiu" in html or "Branzan" in html:
            errors.append(f"PERSONAL NAME FOUND {c}")
        if "From the founder of Snugs.ai, a dad of a toddler building an AI parenting advisor for parents of 0-3 year olds." not in html:
            errors.append(f"AUTHOR TEXT MISSING {c}")
        links = re.findall(r'aria-label="Continue reading".*?</nav>', html, re.S)
        if not links:
            errors.append(f"CONTINUE-READING MISSING {c}")
        else:
            hrefs = re.findall(r'href="(/resources/[^"]+\.html)"', links[0])
            n_links += len(hrefs)
            if not (3 <= len(hrefs) <= 5):
                errors.append(f"LINK COUNT {len(hrefs)} {c}")
            for h in hrefs:
                t = h.lstrip("/")
                if by_path.get(t, {}).get("decision") != "keep":
                    errors.append(f"CORE LINK TO NON-KEEP {c} -> {t}")
        if "data-cta" not in html:
            errors.append(f"CTA MARKUP MISSING {c}")
    print(f"5. core-30 JSON-LD valid, {n_links} contextual internal links OK")

    print(f"counts: {dict(counts)}; sitemap URLs: {len(locs)}; core: {len(core)}")
    if errors:
        print(f"\nFAILED ({len(errors)}):")
        for e in errors[:50]:
            print(" -", e)
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
