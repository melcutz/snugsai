#!/usr/bin/env python3
"""Verify the SEO prune/consolidate work for issue #20 (Prune Pass 2).

Checks:
  1. Every HTML file still parses (html.parser).
  2. Every sitemap URL maps to an existing file that is not noindex.
  3. No noindex page is in the sitemap.
  4. Every redirect target exists and is a keep page.
  5. The JSON-LD on the core 30 is valid JSON with an Article node.
  6. Sitemap count equals indexable set (<=120 articles + tools + top-level).
  7. No noindexed URL in sitemap or resources index pages.
  8. Every 301 target exists locally (file present).
  9. Every indexable page has a self-referencing canonical.
  10. No off-audience indexable titles (AG1, Toniebox, dating, teen, shaving, etc.).
  11. Sitemap.xml is valid XML with lastmod on every URL.
"""

import csv
import json
import re
import sys
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

    # 1. every HTML file parses (resources + top-level + tools + hubs)
    html_files = (
        list((BASE / "resources").glob("*.html"))
        + list((BASE / "resources").rglob("*.html"))
        + [BASE / f for f in ("index.html", "contact.html", "privacy.html", "terms.html")]
        + list((BASE / "tools").glob("*.html"))
    )
    for f in html_files:
        check_parses(f)
    print(f"1. parsed {len(html_files)} HTML files OK")

    # decisions present on disk
    for r in rows:
        p = BASE / r["path"]
        if r["path"].endswith("/"):
            # batch-1 section pages (#19) are directory indexes
            p = p / "index.html"
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

    # 2+3+11. sitemap checks (valid XML, lastmod, no noindex)
    tree = ElementTree.parse(BASE / "sitemap.xml")
    locs = [e.text.strip() for e in tree.getroot().findall("s:url/s:loc", NS)]
    lastmods = [e.text.strip() for e in tree.getroot().findall("s:url/s:lastmod", NS)]
    assert locs, "sitemap has no URLs"
    assert len(locs) == len(lastmods), "every sitemap URL must have lastmod"
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
    print(f"2/3/11. {len(locs)} sitemap URLs map to existing indexable files, all have lastmod, no noindex OK")

    # 4+8. redirect targets exist locally and are keep
    r301 = list(csv.DictReader(open(BASE / "seo" / "redirects-301.csv")))
    for row in r301:
        # Sources stay resources articles; targets may also be the batch-1
        # section hubs/pages (sleep-regressions/...), added in issue #19.
        assert row["from"].startswith(SITE + "/resources/"), row
        assert row["to"].startswith(SITE + "/"), row
        to_rel = row["to"][len(SITE) + 1:]
        from_rel = row["from"][len(SITE) + 1:]
        if not (BASE / to_rel).exists():
            errors.append(f"REDIRECT TARGET MISSING {row['to']}")
        elif to_rel.startswith("resources/") and by_path.get(to_rel, {}).get("decision") != "keep":
            errors.append(f"REDIRECT TARGET NOT KEEP {row['to']}")
        elif to_rel not in by_path and not (BASE / to_rel).is_dir():
            # non-resources targets must be real pages (dirs are their own index)
            errors.append(f"REDIRECT TARGET NOT INDEXABLE {row['to']}")
        if by_path.get(from_rel, {}).get("decision") != "merge":
            errors.append(f"REDIRECT SOURCE NOT MERGE {row['from']}")
    print(f"4/8. {len(r301)} redirect targets exist locally and are keep OK")

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

    # 6. Sitemap count equals indexable set (articles + top-level + tools + hubs)
    keep_articles = [r for r in rows if r["decision"] == "keep"]
    # Prune-pass-2 cap targets resource articles only; batch-1 section pages
    # (tools/, schedules/, sleep-regressions/) are structured, not articles.
    keep_resource_articles = [r for r in keep_articles if r["path"].startswith("resources/")]
    expected_indexable = len(keep_articles) + 6 + 5  # 6 top-level + 5 hubs
    actual_sitemap = len(locs)
    if actual_sitemap != expected_indexable:
        errors.append(f"SITEMAP COUNT MISMATCH: expected {expected_indexable} (keep articles {len(keep_articles)} + 6 top-level + 5 hubs), got {actual_sitemap}")
    if len(keep_resource_articles) > 120:
        errors.append(f"TOO MANY KEEP ARTICLES: {len(keep_resource_articles)} > 120 target")
    print(f"6. sitemap count ({actual_sitemap}) matches indexable set ({expected_indexable}) OK; keep resource articles: {len(keep_resource_articles)} <= 120")

    # 7. No noindexed URL in resources index pages
    # Check resources/index.html
    resources_index = BASE / "resources" / "index.html"
    if resources_index.exists():
        html = resources_index.read_text(encoding="utf-8")
        for n in noindexed:
            if n.replace("resources/", "") in html:
                errors.append(f"NOINDEX PAGE LINKED IN resources/index.html: {n}")
    # Check topic hubs
    for hub in ["pregnancy", "newborn", "baby", "toddler", "dads"]:
        hub_index = BASE / "resources" / hub / "index.html"
        if hub_index.exists():
            html = hub_index.read_text(encoding="utf-8")
            for n in noindexed:
                if n.replace("resources/", "") in html:
                    errors.append(f"NOINDEX PAGE LINKED IN resources/{hub}/index.html: {n}")
    print(f"7. no noindexed URLs in resources index or topic hubs OK")

    # 9. Every indexable page has self-referencing canonical
    indexable_paths = [r["path"] for r in rows if r["decision"] == "keep"]
    indexable_paths += ["index.html", "resources/index.html", "contact.html", "privacy.html", "terms.html", "tools/sleep-milestone-calculator.html"]
    for hub in ["pregnancy", "newborn", "baby", "toddler", "dads"]:
        indexable_paths.append(f"resources/{hub}/index.html")
    
    for path in indexable_paths:
        full_path = BASE / path
        if full_path.is_dir():
            full_path = full_path / "index.html"
        if not full_path.exists():
            errors.append(f"INDEXABLE PAGE MISSING: {path}")
            continue
        html = full_path.read_text(encoding="utf-8")
        canonical_match = re.search(r'<link rel="canonical"\s+href="([^"]+)"', html)
        if not canonical_match:
            errors.append(f"MISSING CANONICAL: {path}")
        else:
            canonical = canonical_match.group(1)
            # Verify it matches expected format
            if path == "index.html":
                expected = f"{SITE}/"
            elif path.endswith("/index.html"):
                expected = f"{SITE}/{path.replace('/index.html', '/')}"
            else:
                expected = f"{SITE}/{path}"
            if canonical != expected:
                errors.append(f"CANONICAL MISMATCH {path}: got {canonical}, expected {expected}")
    print(f"9. {len(indexable_paths)} indexable pages have self-referencing canonical OK")

    # 10. No off-audience indexable titles
    off_audience_keywords = [
        r"\bag1\b", r"\bgruns\b", r"\btoniebox\b", r"\byoto\b",
        r"\bdating\b", r"\bteen\b", r"\bshaving\b",
        r"\bspotify wrapped\b", r"\bxylophone\b",
        r"\bmelissa.*doug\b", r"\bpocket knife\b",
        r"\bwilly wonka\b", r"\bsludge metal\b",
        r"\btattoo\b", r"\broblox\b",
        r"\b529 account\b", r"hospital indemnity",
        r"financial genius", r"ai education for kids",
        r"gifted child", r"babysitter rates in denver",
        r"minnesota", r"rediscover the 80s", r"8-bit christmas",
        r"ultimate family fleet", r"pocket knives",
    ]
    for r in rows:
        if r["decision"] == "keep":
            text = f"{r['title']} {r['path']}".lower()
            for pat in off_audience_keywords:
                if re.search(pat, text):
                    errors.append(f"OFF-AUDIENCE TITLE IN KEEP: {r['path']} - matched {pat}")
    print(f"10. no off-audience titles in indexable pages OK")

    print(f"\ncounts: {dict(counts)}; sitemap URLs: {len(locs)}; core: {len(core)}; keep articles: {len(keep_articles)}")
    if errors:
        print(f"\nFAILED ({len(errors)}):")
        for e in errors[:50]:
            print(" -", e)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()