#!/usr/bin/env python3
"""Generate sitemap.xml from seo/classification.csv + git lastmod dates.

Includes:
  - top-level pages: /, /resources/, /contact.html, /privacy.html,
    /terms.html, /tools/sleep-milestone-calculator.html
  - every `keep` article from seo/classification.csv
Excludes: noindex, merge and remove pages.
lastmod comes from `git log` (last commit touching the file); files never
committed fall back to today's date.
Ensures robots.txt references https://snugs.ai/sitemap.xml.
"""

import csv
import subprocess
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

BASE = Path(__file__).resolve().parent.parent
SITE = "https://snugs.ai"

TOP_LEVEL = [
    ("", "weekly", "1.0"),  # https://snugs.ai/
    ("resources/", "weekly", "0.9"),
    ("contact.html", "monthly", "0.7"),
    ("privacy.html", "monthly", "0.7"),
    ("terms.html", "monthly", "0.7"),
    ("tools/sleep-milestone-calculator.html", "monthly", "0.9"),
]


def git_lastmod(relpath: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%cs", "--", relpath],
            cwd=BASE, text=True,
        ).strip()
        if out:
            return out
    except subprocess.CalledProcessError:
        pass
    return date.today().isoformat()


def main():
    rows = list(csv.DictReader(open(BASE / "seo" / "classification.csv")))
    keep = sorted(r["path"] for r in rows if r["decision"] == "keep")

    urls = []
    for rel, freq, prio in TOP_LEVEL:
        urls.append((f"{SITE}/{rel}", git_lastmod(rel or "."), freq, prio))
    for rel in keep:
        urls.append((f"{SITE}/{rel}", git_lastmod(rel), "monthly", "0.8"))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.1">'
             .replace("0.1", "0.9")]
    for loc, lastmod, freq, prio in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{prio}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    (BASE / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    robots = BASE / "robots.txt"
    text = robots.read_text(encoding="utf-8") if robots.exists() else ""
    if "sitemap.xml" not in text.lower():
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"\nSitemap: {SITE}/sitemap.xml\n"
        robots.write_text(text, encoding="utf-8")
        print("robots.txt: added Sitemap reference")
    else:
        print("robots.txt: Sitemap reference already present")

    print(f"sitemap.xml: {len(urls)} URLs "
          f"({len(TOP_LEVEL)} top-level + {len(keep)} keep articles)")


if __name__ == "__main__":
    main()
