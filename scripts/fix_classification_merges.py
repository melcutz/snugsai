#!/usr/bin/env python3
"""Fix classification: only on-audience clusters with keep targets get merges.
Off-audience clusters: all noindex, no merges."""

import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CLASSIFICATION_CSV = BASE / "seo" / "classification.csv"

# Only these on-audience clusters with keep canonicals get merges
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
    # Separation anxiety -> helping-your-child-through-separation-anxiety-at-night (keep)
    "helping-your-child-through-separation-anxiety-at-night": [
        "helping-your-child-through-nighttime-separation-anxiety-after-parental-divorce",
        "when-your-baby-only-wants-mom-or-dad-navigating-separation-anxiety-with-an-ai-parenting-assistant",
    ],
}

# Off-audience clusters that should be all noindex (no merges)
OFF_AUDIENCE_CANONICALS = [
    "balancing-extracurriculars-with-single-parenthood-strategies-for-juggling-activities",
    "considering-single-motherhood-a-guide-for-aspiring-solo-parents",
    "dating-as-a-single-father-navigating-guilt-and-finding-love",
    "finding-love-and-yourself-again-a-single-parent-s-guide-to-dating-after-heartbreak",
]

# Their duplicates that were incorrectly set to merge
OFF_AUDIENCE_DUPES = [
    "balancing-extracurriculars-with-single-parenthood-when-enough-is-more-than-enough",
    "navigating-extracurricular-activities-with-multiple-young-children-as-a-single-parent",
    "considering-single-motherhood-a-practical-guide-to-preparation",
    "preparing-for-single-motherhood-a-comprehensive-guide-for-prospective-moms",
    "dating-as-a-single-father-balancing-love-life-and-guilt",
    "dating-as-a-single-father-navigating-guilt-selfishness-and-finding-connection",
    "navigating-the-dating-world-as-a-single-father",
    "navigating-online-dating-as-a-parent-to-disclose-or-not-to-disclose",
    "to-disclose-or-not-to-disclose-mentioning-children-in-your-dating-profile",
    "to-share-or-not-to-share-mentioning-children-on-dating-profiles-as-a-single-parent",
    "navigating-childhood-affection-when-kissing-cousins-becomes-a-concern",  # was in separation anxiety but off-audience
]

def main():
    rows = list(csv.DictReader(open(CLASSIFICATION_CSV)))
    by_slug = {r["path"].replace("resources/", "").replace(".html", ""): r for r in rows}
    
    # Revert off-audience canonicals to noindex (they were already noindex)
    for slug in OFF_AUDIENCE_CANONICALS:
        if slug in by_slug:
            by_slug[slug]["decision"] = "noindex"
            by_slug[slug]["merge_target"] = ""
            by_slug[slug]["reason"] = "Not in curated core 0-3 allowlist"
            print(f"Reverted {slug} to noindex")
    
    # Revert off-audience dupes to noindex
    for slug in OFF_AUDIENCE_DUPES:
        if slug in by_slug:
            by_slug[slug]["decision"] = "noindex"
            by_slug[slug]["merge_target"] = ""
            by_slug[slug]["reason"] = "Not in curated core 0-3 allowlist"
            print(f"Reverted {slug} to noindex")
    
    # Apply on-audience merges
    merge_count = 0
    for canonical, dupes in MERGE_CLUSTERS.items():
        if canonical not in by_slug:
            print(f"WARNING: Canonical not found: {canonical}")
            continue
        canonical_row = by_slug[canonical]
        if canonical_row["decision"] != "keep":
            print(f"  WARNING: Canonical {canonical} is not keep ({canonical_row['decision']}), skipping")
            continue
        
        for dupe in dupes:
            if dupe not in by_slug:
                print(f"  WARNING: Duplicate not found: {dupe}")
                continue
            dupe_row = by_slug[dupe]
            if dupe_row["decision"] == "merge" and dupe_row["merge_target"] == f"resources/{canonical}.html":
                continue  # already correct
            dupe_row["decision"] = "merge"
            dupe_row["merge_target"] = f"resources/{canonical}.html"
            dupe_row["reason"] = f"Near-duplicate; canonical: {canonical}"
            merge_count += 1
            print(f"  MERGE: {dupe} -> {canonical}")
    
    # Rebuild rows from by_slug preserving order
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
    
    print(f"\nApplied {merge_count} merge updates")
    
    # Print summary
    counts = {}
    for r in rows:
        counts[r["decision"]] = counts.get(r["decision"], 0) + 1
    print(f"Summary: {counts}")

if __name__ == "__main__":
    main()