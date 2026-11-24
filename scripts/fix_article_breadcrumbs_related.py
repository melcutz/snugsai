#!/usr/bin/env python3
"""Fix article breadcrumbs, JSON-LD schema, and Related Guides for issue #34.

This script updates all resource articles in resources/*.html:
  1. Sets visible breadcrumb last item to that article's own title (linking nowhere).
  2. Updates JSON-LD BreadcrumbList item 3 name to that article's own title.
  3. Removes leftover 'Calm a Crying Baby' HowTo schema from non-calm articles.
  4. Replaces the ~468-link Related Guides dump with 8 on-topic links to keep articles.
"""

import csv
import html
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RESOURCES = BASE / "resources"

# Topic clusters for scoring relevance
TOPICS = {
    "sleep": [
        "nap", "naps", "sleep", "bedtime", "regression", "co-sleep", "snoo",
        "cradlewise", "swaddle", "wake", "night", "lullab", "huckleberry",
        "smart sleep", "contact nap", "settl", "slumber"
    ],
    "feeding": [
        "breastfeed", "bottle", "formula", "solids", "milk", "wean", "latch",
        "food", "eating", "mealtime", "hunger", "snack", "eat", "pumping"
    ],
    "behavior": [
        "tantrum", "aggressi", "biting", "hitting", "whining", "velcro",
        "meltdown", "discipline", "boundary", "playtime", "independent",
        "overstimul", "no phase", "chaos", "temperament", "clingy"
    ],
    "potty": [
        "potty", "diaper", "blowout", "poop", "constipat", "perianal"
    ],
    "milestones": [
        "milestone", "word", "speech", "babble", "talk", "walk", "crawl",
        "develop", "language", "read", "audio", "hearing", "motor"
    ],
    "pregnancy_postpartum": [
        "pregnan", "postpartum", "labor", "delivery", "preeclampsia",
        "childbirth", "expecting", "new mom", "hospital", "partner leave",
        "anorexia", "trimester", "recovery"
    ],
    "health_safety": [
        "rsv", "fever", "cough", "medicine", "fell", "safety", "safe",
        "bath", "hair", "teeth", "tooth", "cleaning", "lock", "rehome"
    ],
    "dads": [
        "dad", "father", "paternal", "dada", "paternity"
    ],
    "newborn": [
        "newborn", "infant", "0-3", "colic", "grunting", "fussy", "crying",
        "sooth", "swaddl"
    ],
    "toddler": [
        "toddler", "2-year", "3-year", "18-month", "terrible", "preschool"
    ],
}

STOP_WORDS = {
    "and", "the", "for", "with", "what", "your", "how", "when", "why",
    "from", "into", "that", "this", "tips", "guide", "parents", "parenting",
    "more", "than", "over", "under", "about", "after", "before", "during",
    "navigating", "understanding", "managing", "helping", "surviving"
}


def load_keep_articles():
    csv_path = BASE / "seo" / "classification.csv"
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    keep_rows = [r for r in rows if r["decision"] == "keep" and r["path"].startswith("resources/")]
    
    articles = []
    for r in keep_rows:
        slug = r["path"].replace("resources/", "").replace(".html", "")
        title = r["title"].replace(" | Snugs.ai", "").strip()
        text = f"{slug} {title}".lower()
        articles.append({
            "slug": slug,
            "title": title,
            "path": r["path"],
            "text": text,
            "words": set(re.findall(r"\b[a-z]{3,}\b", text)) - STOP_WORDS,
            "topics": {t for t, kws in TOPICS.items() if any(kw in text for kw in kws)},
        })
    return articles


def get_related_articles(target_slug, target_title, all_keep_articles, count=8):
    target_text = f"{target_slug} {target_title}".lower()
    target_words = set(re.findall(r"\b[a-z]{3,}\b", target_text)) - STOP_WORDS
    target_topics = {t for t, kws in TOPICS.items() if any(kw in target_text for kw in kws)}
    
    scores = []
    for a in all_keep_articles:
        if a["slug"] == target_slug:
            continue
        score = 0
        common_words = target_words & a["words"]
        score += len(common_words) * 3
        
        common_topics = target_topics & a["topics"]
        score += len(common_topics) * 5
        
        # Deterministic sorting: higher score first, then shorter slug, then alphabetical
        scores.append((score, a["slug"], a))
    
    scores.sort(key=lambda x: (x[0], -len(x[1]), x[1]), reverse=True)
    return [s[2] for s in scores[:count]]


def fix_article(file_path: Path, all_keep_articles):
    content = file_path.read_text(encoding="utf-8")
    
    # Skip index and redirect stubs
    if file_path.name == "index.html" or 'http-equiv="refresh"' in content:
        return False, "skipped (index or redirect)"
    
    # Extract title
    title_match = re.search(r"<title>(.*?)</title>", content, re.S)
    if not title_match:
        return False, "no title found"
    
    raw_title = title_match.group(1).strip()
    article_title = raw_title.replace(" | Snugs.ai", "").strip()
    slug = file_path.stem
    
    modified = content
    
    # 1. Update visible breadcrumb nav last item
    escaped_title = html.escape(article_title, quote=False)
    nav_pattern = r'(<nav class="text-sm text-gray-600 mb-6 animate-fadeIn">.*?<span class="text-gray-800">).*?(</span>\s*</nav>)'
    if not re.search(nav_pattern, modified, re.S):
        return False, "breadcrumb nav pattern not found"
    modified = re.sub(
        nav_pattern,
        lambda m: m.group(1) + escaped_title + m.group(2),
        modified,
        count=1,
        flags=re.S
    )
    
    # 2. Update JSON-LD BreadcrumbList item 3
    item3_pattern = r'\{\s*"@type":\s*"ListItem",\s*"position":\s*3,\s*"name":\s*.*?\s*"item":\s*"[^"]*"\s*\}'
    if not re.search(item3_pattern, modified, re.S):
        return False, "BreadcrumbList item 3 pattern not found"
    new_item3 = (
        '{\n'
        '          "@type": "ListItem",\n'
        '          "position": 3,\n'
        f'          "name": {json.dumps(article_title)},\n'
        f'          "item": "https://snugs.ai/resources/{slug}.html"\n'
        '        }'
    )
    modified = re.sub(
        item3_pattern,
        lambda m: new_item3,
        modified,
        count=1,
        flags=re.S
    )
    
    # 3. Remove leftover HowTo schema from non-calm articles
    if slug != "calm-a-crying-baby":
        howto_pattern = r'\s*<script type="application/ld\+json">\s*\{\s*"@context":\s*"https://schema.org",\s*"@type":\s*"HowTo".*?</script>'
        modified = re.sub(howto_pattern, "", modified, flags=re.S)
    
    # 4. Replace Related Guides section
    related = get_related_articles(slug, article_title, all_keep_articles, count=8)
    lis = "\n".join(
        f'        <li><a href="/resources/{r["slug"]}.html" class="text-orange-700 underline hover:text-orange-800 font-medium transition-colors">{html.escape(r["title"])}</a></li>'
        for r in related
    )
    new_related_section = (
        '    <section class="mt-10 pt-8 border-t-2 border-orange-100">\n'
        '      <h2 class="text-2xl font-display font-semibold text-gray-800 mb-4">Related Guides</h2>\n'
        '      <ul class="space-y-2 text-gray-700">\n'
        f'{lis}\n'
        '      </ul>\n'
        '    </section>'
    )
    rg_pattern = r'<section class="mt-10 pt-8 border-t-2 border-orange-100">\s*<h2[^>]*>Related Guides</h2>\s*<ul[^>]*>.*?</ul>\s*</section>'
    if not re.search(rg_pattern, modified, re.S):
        return False, "Related Guides section pattern not found"
    modified = re.sub(
        rg_pattern,
        lambda m: new_related_section,
        modified,
        count=1,
        flags=re.S
    )
    
    file_path.write_text(modified, encoding="utf-8")
    return True, f"updated with {len(related)} related guides"


def main():
    keep_articles = load_keep_articles()
    print(f"Loaded {len(keep_articles)} keep resource articles for Related Guides.")
    
    all_files = sorted(RESOURCES.glob("*.html"))
    updated_count = 0
    skipped_count = 0
    errors = []
    
    for f in all_files:
        ok, msg = fix_article(f, keep_articles)
        if ok:
            updated_count += 1
        elif "skipped" in msg:
            skipped_count += 1
        else:
            errors.append(f"{f.name}: {msg}")
            
    print(f"Results: {updated_count} articles updated, {skipped_count} skipped.")
    if errors:
        print(f"Errors ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")
        raise SystemExit(1)
    print("All article breadcrumbs, JSON-LD, and Related Guides successfully fixed.")


if __name__ == "__main__":
    main()
