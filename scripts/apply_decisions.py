#!/usr/bin/env python3
"""Apply seo/classification.csv decisions to resource HTML files.

- noindex pages: insert <meta name="robots" content="noindex, follow"> in <head>.
- merge pages: replace with a minimal redirect stub (canonical to target,
  robots noindex, meta refresh, visible link). Writes seo/redirects-301.csv
  (from,to as full URLs) for future Cloudflare 301s.
- keep/remove: untouched.

Idempotent: skips files that already carry the robots noindex tag; stubs are
only written for pages still classified merge.
"""

import csv
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SITE = "https://snugs.ai"
ROBOTS_TAG = '<meta name="robots" content="noindex, follow">'


def add_noindex(html: str) -> str:
    if "noindex" in html:
        return html  # already handled
    # Insert right before the canonical link when present, else after <head>.
    if '<link rel="canonical"' in html:
        return html.replace(
            '<link rel="canonical"', ROBOTS_TAG + '\n  <link rel="canonical"', 1
        )
    return re.sub(r"(<head[^>]*>)", r"\1\n  " + ROBOTS_TAG, html, count=1)


def redirect_stub(title: str, target_url: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title} | Snugs.ai</title>
  <link rel="canonical" href="{target_url}" />
  {ROBOTS_TAG}
  <meta http-equiv="refresh" content="0; url={target_url}" />
</head>
<body>
  <main style="font-family: system-ui, sans-serif; max-width: 640px; margin: 4rem auto; padding: 0 1rem;">
    <h1>{title}</h1>
    <p>This article has moved. <a href="{target_url}">Continue reading here</a>.</p>
  </main>
</body>
</html>
"""


def main():
    rows = list(csv.DictReader(open(BASE / "seo" / "classification.csv")))
    redirects = []
    n_noindex = n_merge = 0
    for r in rows:
        path = BASE / r["path"]
        if r["decision"] == "noindex":
            html = path.read_text(encoding="utf-8")
            new = add_noindex(html)
            if new != html:
                path.write_text(new, encoding="utf-8")
                n_noindex += 1
        elif r["decision"] == "merge":
            target = r["merge_target"]  # e.g. resources/slug.html
            target_url = f"{SITE}/{target}"
            m = re.search(r"<title>(.*?)</title>", path.read_text(encoding="utf-8"))
            title = (m.group(1).split(" | ")[0] if m else target)[:150]
            path.write_text(redirect_stub(title, target_url), encoding="utf-8")
            n_merge += 1
            redirects.append((f"{SITE}/{r['path']}", target_url))
        # Always collect redirects for merge decisions to keep redirects-301.csv in sync
        if r["decision"] == "merge":
            target = r["merge_target"]
            target_url = f"{SITE}/{target}"
            redirects.append((f"{SITE}/{r['path']}", target_url))

    with open(BASE / "seo" / "redirects-301.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["from", "to"])
        w.writerows(sorted(set(redirects)))  # deduplicate

    print(f"noindex tags added: {n_noindex}, merge stubs written: {n_merge}")
    print(f"redirects-301.csv rows: {len(set(redirects))}")


if __name__ == "__main__":
    main()
