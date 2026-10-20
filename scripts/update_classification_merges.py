#!/usr/bin/env python3
"""Update classification.csv with merge decisions for duplicate clusters from plan 3.2.
Only merge clusters where the canonical is a keep page (on-audience).
Off-audience clusters stay as noindex (no 301 needed)."""

import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CLASSIFICATION_CSV = BASE / "seo" / "classification.csv"

# Only on-audience duplicate clusters with keep canonicals
MERGE_CLUSTERS = {
    # Toddler sleep battles -> help-your-toddler-sleep-expert-tips-for-tired-parents (keep)
    "help-your-toddler-sleep-expert-tips-for-tired-parents": [
        "conquering-sleep-battles-a-guide-for-parents-of-toddlers-who-fight-sleep",
        "conquering-the-sleep-struggle-a-guide-for-parents-of-toddlers-who-fight-sleep",
        "conquering-the-toddler-sleep-battle-strategies-for-exhausted-parents",
        "conquering-the-toddler-sleep-struggle-tips-for-exhausted-parents",
        "taming-the-bedtime-dragon-strategies-for-parents-of-needy-toddlers",
        "navigating-toddler-sleep-struggles-strategies-for-peaceful-bedtimes",
        "the-struggle-is-real-navigating-sleep-battles-with-your-child",
    ],
    # Dad pregnancy guides -> dad-s-guide-to-pregnancy-and-childbirth-essential-tips-for-expecting-fathers (keep)
    "dad-s-guide-to-pregnancy-and-childbirth-essential-tips-for-expecting-fathers": [
        "a-dad-s-guide-to-preparing-for-parenthood",
        "dad-s-guide-to-navigating-pregnancy-and-childbirth",
        "dad-tips-for-expecting-parents-a-comprehensive-guide",
        "dad-tips-preparing-for-parenthood",
        "navigating-labor-day-a-new-dad-s-guide-to-supporting-your-partner-and-welcoming-your-son",
    ],
    # Custody 2-2-3 -> navigating-2-2-3-custody-schedules-with-toddlers-a-parent-s-guide (keep)
    "navigating-2-2-3-custody-schedules-with-toddlers-a-parent-s-guide": [
        "navigating-2-2-3-custody-schedules-with-toddlers-is-it-too-much-for-your-almost-2-year-old",
    ],
    # Separation anxiety -> helping-your-child-through-separation-anxiety-at-night 
    # This one is noindex but it's on-audience (toddler separation anxiety). Let's make it keep.
    "helping-your-child-through-separation-anxiety-at-night": [
        "helping-your-child-through-nighttime-separation-anxiety-after-parental-divorce",
        "when-your-baby-only-wants-mom-or-dad-navigating-separation-anxiety-with-an-ai-parenting-assistant",
    ],
}

def main():
    rows = list(csv.DictReader(open(CLASSIFICATION_CSV)))
    by_slug = {r["path"].replace("resources/", "").replace(".html", ""): r for r in rows}
    
    # First, promote the separation anxiety canonical to keep
    sep_slug = "helping-your-child-through-separation-anxiety-at-night"
    if sep_slug in by_slug:
        by_slug[sep_slug]["decision"] = "keep"
        by_slug[sep_slug]["reason"] = "Explicitly curated core 0-3 article (separation anxiety canonical)"
        print(f"Promoted {sep_slug} to keep")
    
    merge_count = 0
    for canonical, dupes in MERGE_CLUSTERS.items():
        if canonical not in by_slug:
            print(f"WARNING: Canonical not found: {canonical}")
            continue
        canonical_row = by_slug[canonical]
        print(f"Canonical: {canonical} (decision: {canonical_row['decision']})")
        
        if canonical_row["decision"] != "keep":
            print(f"  WARNING: Canonical is not keep, skipping merges")
            continue
        
        for dupe in dupes:
            if dupe not in by_slug:
                print(f"  WARNING: Duplicate not found: {dupe}")
                continue
            dupe_row = by_slug[dupe]
            if dupe_row["decision"] in ("keep", "merge"):
                print(f"  SKIP: {dupe} already {dupe_row['decision']}")
                continue
            # Update to merge
            dupe_row["decision"] = "merge"
            dupe_row["merge_target"] = f"resources/{canonical}.html"
            dupe_row["reason"] = f"Near-duplicate; canonical: {canonical}"
            merge_count += 1
            print(f"  MERGE: {dupe} -> {canonical}")
    
    # Rebuild rows from by_slug to preserve order
    # Actually, let's preserve original order by updating in place
    for r in rows:
        slug = r["path"].replace("resources/", "").replace(".html", "")
        if slug in by_slug:
            r["decision"] = by_slug[slug]["decision"]
            r["merge_target"] = by_slug[slug]["merge_target"]
            r["reason"] = by_slug[slug]["reason"]
    
    # Write updated classification
    with open(CLASSIFICATION_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "title", "decision", "merge_target", "reason"])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\nUpdated {merge_count} articles to merge")
    
    # Print summary
    counts = {}
    for r in rows:
        counts[r["decision"]] = counts.get(r["decision"], 0) + 1
    print(f"Summary: {counts}")

if __name__ == "__main__":
    main()