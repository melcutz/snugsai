#!/usr/bin/env python3
"""Generate PRODUCT_INVENTORY.md listing every page and tool."""

import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# Read classification
rows = list(csv.DictReader(open(BASE / "seo" / "classification.csv")))
by_path = {r["path"]: r for r in rows}

# All HTML files
all_files = []

# Top-level pages
top_level = [
    ("index.html", "Homepage", True),
    ("contact.html", "Contact page", True),
    ("privacy.html", "Privacy policy", True),
    ("terms.html", "Terms of service", True),
    ("resources/index.html", "Resources hub (topic index)", True),
    ("tools/sleep-milestone-calculator.html", "Sleep milestone calculator tool", True),
]

for rel, purpose, indexable in top_level:
    all_files.append((rel, purpose, indexable))

# Hub pages
hubs = [
    ("resources/pregnancy/index.html", "Pregnancy guides hub", True),
    ("resources/newborn/index.html", "Newborn (0-3mo) guides hub", True),
    ("resources/baby/index.html", "Baby (4-12mo) guides hub", True),
    ("resources/toddler/index.html", "Toddler (1-3yr) guides hub", True),
    ("resources/dads/index.html", "Dad guides hub", True),
]

for rel, purpose, indexable in hubs:
    all_files.append((rel, purpose, indexable))

# Resource articles
for r in rows:
    rel = r["path"]
    title = r["title"].split(" | ")[0]
    decision = r["decision"]
    indexable = decision == "keep"
    purpose = title
    all_files.append((rel, purpose, indexable))

# Sort by path
all_files.sort(key=lambda x: x[0])

# Write markdown
output_path = BASE / "docs" / "PRODUCT_INVENTORY.md"
output_path.parent.mkdir(exist_ok=True)

with open(output_path, "w", encoding="utf-8") as f:
    f.write("# Product Inventory\n\n")
    f.write(f"Generated: {__import__('datetime').date.today().isoformat()}\n\n")
    f.write("| Path | Purpose | Indexable |\n")
    f.write("|------|---------|-----------|\n")
    
    indexable_count = 0
    for rel, purpose, indexable in all_files:
        idx_str = "Yes" if indexable else "No"
        if indexable:
            indexable_count += 1
        f.write(f"| {rel} | {purpose} | {idx_str} |\n")
    
    f.write(f"\n**Total pages:** {len(all_files)}  \n")
    f.write(f"**Indexable pages:** {indexable_count}  \n")
    f.write(f"**Noindex/merge/remove pages:** {len(all_files) - indexable_count}  \n")

print(f"Written to {output_path}")
print(f"Total: {len(all_files)}, Indexable: {indexable_count}")