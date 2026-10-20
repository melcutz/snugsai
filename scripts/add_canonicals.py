#!/usr/bin/env python3
"""Add self-referencing canonical tags to all indexable pages."""

import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SITE = "https://snugs.ai"

# Read classification to get keep articles
rows = list(csv.DictReader(open(BASE / "seo" / "classification.csv")))
keep_articles = [r for r in rows if r["decision"] == "keep"]

def add_canonical_to_file(filepath, canonical_url):
    """Add or update self-referencing canonical tag."""
    html = filepath.read_text(encoding="utf-8")
    
    # Check if canonical already exists
    if '<link rel="canonical"' in html:
        # Replace existing canonical
        import re
        html = re.sub(
            r'<link rel="canonical"[^>]*>',
            f'<link rel="canonical" href="{canonical_url}" />',
            html
        )
    else:
        # Insert after <head>
        html = html.replace('<head>', f'<head>\n  <link rel="canonical" href="{canonical_url}" />', 1)
    
    filepath.write_text(html, encoding="utf-8")

# Add canonicals to keep articles
for article in keep_articles:
    path = BASE / article["path"]
    slug = article["path"].replace("resources/", "").replace(".html", "")
    canonical_url = f"{SITE}/resources/{slug}.html"
    add_canonical_to_file(path, canonical_url)

# Add canonicals to hub pages
for hub in ["pregnancy", "newborn", "baby", "toddler", "dads"]:
    path = BASE / "resources" / hub / "index.html"
    canonical_url = f"{SITE}/resources/{hub}/"
    add_canonical_to_file(path, canonical_url)

# Add canonicals to top-level pages
top_level = [
    ("index.html", f"{SITE}/"),
    ("resources/index.html", f"{SITE}/resources/"),
    ("contact.html", f"{SITE}/contact.html"),
    ("privacy.html", f"{SITE}/privacy.html"),
    ("terms.html", f"{SITE}/terms.html"),
    ("tools/sleep-milestone-calculator.html", f"{SITE}/tools/sleep-milestone-calculator.html"),
]

for rel_path, canonical_url in top_level:
    path = BASE / rel_path
    if path.exists():
        add_canonical_to_file(path, canonical_url)

print(f"Added canonicals to {len(keep_articles)} keep articles + 5 hubs + 6 top-level pages")

# Verify noindex pages have noindex tag (not canonical pointing to themselves)
noindex_articles = [r for r in rows if r["decision"] == "noindex"]
for article in noindex_articles:
    path = BASE / article["path"]
    html = path.read_text(encoding="utf-8")
    if 'noindex' not in html:
        print(f"WARNING: noindex page missing noindex tag: {article['path']}")

print("Done.")