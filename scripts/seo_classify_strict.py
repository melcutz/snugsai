#!/usr/bin/env python3
"""Strict SEO classification for Snugs.ai resources (Prune Pass 2) - Curated Allowlist.

Audience rule (STRICT):
  keep    = ONLY explicitly listed high-quality core 0-3 articles (~100-120 target).
  noindex = everything else (off-audience, thin, fluff, general parenting).
  merge   = near-duplicate articles on the same core topic (strongest kept as
            merge_target).
  remove  = empty/broken pages only. Conservative: prefer noindex over remove.
"""

import csv
import re
from html.parser import HTMLParser
from pathlib import Path


class ResourceHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.h1 = ""
        self.meta_description = ""
        self.in_title = False
        self.in_h1 = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.in_h1 = True
        elif tag == "meta":
            if attrs_dict.get("name") == "description":
                self.meta_description = attrs_dict.get("content", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "h1":
            self.in_h1 = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.in_h1:
            self.h1 += data


def parse_html_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    parser = ResourceHTMLParser()
    parser.feed(content)
    return {
        "title": parser.title.strip(),
        "h1": parser.h1.strip(),
        "meta_description": parser.meta_description.strip(),
        "size": len(content),
    }


# -----------------------------------------------------------------------------
# EXPLICIT ALLOWLIST: Only these slugs are kept as indexable.
# Curated for high-quality, core 0-3 parenting content.
# Target: ~100-120 articles.
# -----------------------------------------------------------------------------
KEEP_SLUGS = {
    # PREGNANCY & POSTPARTUM (12)
    "navigating-an-unplanned-pregnancy-with-an-existing-child-and-long-distance-relationship-challenges",
    "navigating-intimacy-and-low-libido-postpartum-a-guide-for-new-parents",
    "navigating-marital-strain-with-a-newborn-when-to-seek-help",
    "navigating-newborn-challenges-when-reality-doesn-t-match-expectations",
    "navigating-postpartum-depression-understanding-intrusive-thoughts-and-seeking-support",
    "navigating-postpartum-exhaustion-and-partner-support-you-re-not-alone",
    "navigating-postpartum-identity-crisis-more-than-just-mom",
    "navigating-postpartum-medical-bills-a-guide-for-new-parents",
    "navigating-postpartum-stress-when-your-partner-doesn-t-appreciate-your-efforts",
    "navigating-relationship-challenges-as-new-parents-a-guide-to-communication-and-support",
    "navigating-relationship-challenges-with-a-newborn-a-new-parent-s-guide",
    "navigating-relationship-struggles-and-co-parenting-with-a-new-baby",
    "navigating-unexpected-hospital-stays-during-pregnancy-a-guide-for-dads",
    "postpartum-body-image-navigating-anorexia-recovery-and-the-myth-of-weight-falling-off-while-breastfeeding",
    "postpartum-survival-guide-tips-for-navigating-life-with-a-newborn-and-a-toddler",
    "taking-a-night-off-self-care-for-breastfeeding-mothers",
    "the-guilt-of-glamour-embracing-your-postpartum-self",
    "the-unspeakable-joy-of-new-parenthood-embracing-the-love-even-with-little-sleep",
    "navigating-early-days-postpartum-overwhelm-and-finding-your-footing",
    "managing-postpartum-preeclampsia-and-anxiety-a-guide-for-new-parents",
    "managing-postpartum-rage-towards-your-toddler",
    "navigating-partner-leave-after-a-new-job-a-guide-for-new-parents",

    # NEWBORN (0-3 months) (12)
    "baby-bath-safety-preventing-and-managing-accidental-burns",
    "baby-fell-off-the-bed-what-to-do-when-your-infant-falls",
    "baby-safety-during-breastfeeding-addressing-suffocation-fears",
    "calm-a-crying-baby",
    "coping-with-rsv-in-your-3-month-old-tips-for-sleep-and-sanity",
    "engaging-your-3-month-old-simple-playtime-ideas-for-new-parents",
    "essential-newborn-checklist-what-you-absolutely-need-for-your-little-one",
    "keeping-baby-s-room-at-a-safe-and-comfortable-temperature",
    "keeping-your-baby-s-underarms-clean-and-healthy-a-guide-for-new-parents",
    "keeping-your-newborn-healthy-when-you-have-a-toddler-in-daycare",
    "newborn-sleep-schedule-weeks-1-12",
    "perianal-skin-tags-in-babies-when-to-worry-about-bleeding",
    "post-delivery-diaper-needs-what-new-moms-should-know",
    "protecting-your-newborn-from-daycare-germs-tips-for-parents-with-toddlers",
    "safe-swaddling-how-to",
    "screen-time-for-infants-understanding-the-risks-and-recommendations",
    "soothing-a-fussy-baby-tips-for-diaper-changes-and-feeding-with-reflux",
    "surviving-the-fussy-baby-phase-tips-for-exhausted-parents",
    "surviving-the-newborn-phase-dealing-with-fussy-babies-and-parental-exhaustion",
    "surviving-the-newborn-stage-when-your-baby-won-t-sleep-and-you-ve-reached-your-breaking-point",
    "understanding-and-soothing-your-grunting-baby-a-guide-for-new-parents",
    "understanding-baby-fussiness-before-a-poop-a-common-newborn-stage",
    "understanding-baby-s-milk-intake-why-it-s-unpredictable-and-what-to-expect",
    "unusual-baby-sleeping-positions-when-to-worry-and-when-to-relax",
    "when-to-take-your-baby-to-the-dentist-expert-advice-and-parent-experiences",
    "when-your-baby-cries-constantly-navigating-colic-and-persistent-crying",

    # BABY (4-12 months) (10)
    "baby-not-pooping-after-starting-solids-what-s-normal-and-when-to-worry",
    "baby-tooth-decay-understanding-and-preventing-cavities-in-infants",
    "helping-your-baby-through-teething-illness-and-sleep-disruptions",
    "hunger-vs-tired-cues",
    "mastering-baby-naps-from-contact-naps-to-independent-sleep",
    "navigating-baby-s-digestive-upset-when-starting-solids",
    "navigating-baby-sleep-why-following-cues-can-be-a-christmas-miracle",
    "navigating-the-4-month-sleep-regression-tips-for-new-parents",
    "navigating-the-12-week-sleep-regression-tips-for-new-parents",
    "when-your-9-month-old-won-t-sleep-a-parent-s-guide-to-overcoming-severe-sleep-disturbances",

    # TODDLER (1-3 years) (30)
    "are-girls-really-early-talkers-exploring-language-development-in-toddlers",
    "celebrating-toddler-milestones-navigating-language-development-and-parental-pride",
    "celebrating-your-baby-s-first-birthday-intimate-ideas-for-parents-and-baby",
    "cracking-the-toddler-code-how-one-parent-turned-playtime-into-mealtime",
    "creating-effective-visual-routine-charts-for-toddlers",
    "embrace-the-silly-fun-and-weird-games-to-play-with-your-toddler",
    "help-your-toddler-sleep-expert-tips-for-tired-parents",
    "helping-your-child-overcome-potty-training-setbacks-and-school-toilet-anxiety",
    "how-to-get-your-3-year-old-to-stay-in-their-room-at-night",
    "managing-aggressive-behavior-in-toddlers-a-guide-for-dads",
    "navigating-2-2-3-custody-schedules-with-toddlers-a-parent-s-guide",
    "navigating-aggression-in-3-year-olds-what-to-do-when-gentle-parenting-isn-t-enough",
    "navigating-cold-weather-with-your-toddler-safety-tips-for-outdoor-events",
    "navigating-daycare-what-to-expect-and-when-to-worry-for-your-baby",
    "navigating-developmental-milestones-with-a-preemie-a-parent-s-guide-to-torticollis-and-muscle-tone",
    "navigating-feeding-fears-a-parent-s-guide-to-mealtime-anxiety",
    "navigating-funerals-with-a-toddler-tips-for-a-difficult-day",
    "navigating-grief-with-young-children-talking-to-your-kids-about-loss",
    "navigating-the-18-month-sleep-regression-why-your-toddler-is-suddenly-clingy-and-how-to-help",
    "navigating-the-2-year-age-gap-success-stories-and-tips-for-parents",
    "navigating-the-mine-phase-strategies-for-parents-of-toddlers",
    "navigating-the-no-phase-when-your-3-year-old-stops-saying-yes",
    "navigating-the-storm-understanding-and-managing-your-3-year-old-s-tantrums",
    "navigating-the-terrible-threes-understanding-and-managing-challenging-behavior-in-toddlers",
    "navigating-the-terrible-twos-and-threes-and-fours-managing-constant-crying-and-defiance",
    "navigating-toddler-independence-when-privacy-and-potty-training-collide",
    "navigating-toddler-overstimulation-what-to-do-when-fun-turns-overwhelming",
    "navigating-toddler-tantrums-and-aggression-when-is-it-normal-and-how-to-help",
    "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond",
    "potty-training-a-toddler-while-managing-a-newborn-tips-for-stressed-parents",
    "potty-training-resistance-strategies-for-a-nearly-4-year-old",
    "potty-training-toddlers-overcoming-fear-and-building-independence",
    "transitioning-your-toddler-to-a-bed-advice-for-a-smooth-move",
    "understanding-and-managing-severe-constipation-in-toddlers-a-parent-s-guide",
    "understanding-and-managing-toddler-jealousy-a-parent-s-guide",
    "understanding-yes-and-no-a-developmental-guide-for-toddlers",
    "understanding-your-baby-s-temperament-why-some-babies-are-harder-than-others",
    "using-timers-to-help-toddlers-transition-a-parent-s-guide",
    "when-does-a-babble-become-a-word-understanding-your-baby-s-first-words",
    "when-toddlers-lock-you-out-parenting-mishaps-and-how-to-survive-them",

    # DAD OF YOUNG KIDS (8)
    "beyond-sleep-deprivation-navigating-the-real-challenges-of-new-fatherhood",
    "conquering-the-laundry-mountain-tips-for-dads",
    "dad-s-guide-to-pregnancy-and-childbirth-essential-tips-for-expecting-fathers",
    "navigating-new-fatherhood-finding-positivity-and-support",
    "navigating-the-chaos-tips-for-dads-welcoming-baby-3",
    "navigating-the-dada-tax-understanding-baby-s-preference-and-your-role-as-a-new-father",
    "the-importance-of-paternal-responsibility-in-parenting",
    "the-journey-to-fatherhood-understanding-the-adoption-process",
    "the-power-of-the-dad-network-how-fathers-support-each-other-in-times-of-need",

    # ADDITIONAL CANONICALS FOR MERGE GROUPS (core 0-3 content)
    "maintaining-a-tidy-home-with-a-baby-tips-for-busy-parents",
    "navigating-online-communities-addressing-spam-and-maintaining-focus-in-single-parent-forums",
    "navigating-work-as-a-single-mom-with-a-young-child-strategies-for-success",
    "rediscovering-femininity-after-motherhood-tips-for-new-moms",
    "smart-shopping-for-growing-kids-a-parent-s-guide-to-budget-friendly-wardrobes",
    "surviving-holiday-travel-with-a-baby-tips-and-tricks",
    "the-importance-of-getting-young-children-out-of-the-house-addressing-differing-parental-views",
    "thoughtful-gift-ideas-for-your-child-s-parent-after-separation",
    "hilarious-and-heartwarming-things-kids-say-a-parent-s-guide",
}

# -----------------------------------------------------------------------------
# 3. Curated merge groups: canonical slug -> [duplicate slugs].
#    Canonical must exist and be classified keep.
# -----------------------------------------------------------------------------
MERGE_GROUPS = {
    "hilarious-and-heartwarming-things-kids-say-a-parent-s-guide": [
        "hilarious-and-heartwarming-things-kids-say-a-parenting-round-up",
        "hilarious-and-heartwarming-things-kids-say-a-parenting-roundup",
        "hilarious-and-heartwarming-things-kids-say-a-parenting-treasure-trove",
    ],
    "rediscovering-femininity-after-motherhood-tips-for-new-moms": [
        "rediscovering-your-femininity-after-motherhood-tips-for-new-moms",
    ],
    "navigating-relationship-challenges-as-new-parents-a-guide-to-communication-and-support": [
        "navigating-relationship-challenges-as-new-parents-a-guide",
        "navigating-relationship-challenges-as-new-parents",
        "navigating-relationship-challenges-in-early-parenthood-insights-from-the-newparents-community",
    ],
    "potty-training-a-toddler-while-managing-a-newborn-tips-for-stressed-parents": [
        "potty-training-a-toddler-with-a-newborn-strategies-for-success",
    ],
    "navigating-work-as-a-single-mom-with-a-young-child-strategies-for-success": [
        "navigating-work-as-a-single-mom-with-young-children-strategies-and-support",
    ],
    "maintaining-a-tidy-home-with-a-baby-tips-for-busy-parents": [
        "maintaining-a-tidy-home-with-a-baby-tips-for-clean-parents",
    ],
    "navigating-online-communities-addressing-spam-and-maintaining-focus-in-single-parent-forums": [
        "navigating-online-communities-dealing-with-spam-and-maintaining-focus-in-single-parent-forums",
        "navigating-online-communities-dealing-with-spam-and-maintaining-focus-in-single-parent-subreddits",
    ],
    "surviving-holiday-travel-with-a-baby-tips-and-tricks": [
        "surviving-holiday-travel-with-a-baby-tips-for-parents",
    ],
    "smart-shopping-for-growing-kids-a-parent-s-guide-to-budget-friendly-wardrobes": [
        "smart-strategies-for-buying-clothes-for-growing-kids-on-a-budget",
    ],
    "when-toddlers-lock-you-out-parenting-mishaps-and-how-to-survive-them": [
        "when-toddlers-become-tiny-jailers-lessons-learned-from-being-locked-out-in-the-cold",
    ],
    "toniebox-vs-yoto-player-which-audio-player-is-right-for-your-toddler": [
        "toniebox-vs-yoto-player-which-is-the-best-audio-companion-for-toddlers",
    ],
    "navigating-the-terrible-threes-understanding-and-managing-challenging-behavior-in-toddlers": [
        "navigating-the-terrible-threes-understanding-and-managing-tantrums-in-3-5-year-olds",
    ],
    "navigating-2-2-3-custody-schedules-with-toddlers-a-parent-s-guide": [
        "navigating-2-2-3-custody-schedules-with-toddlers-is-it-too-much-for-your-almost-2-year-old",
    ],
    "help-your-toddler-sleep-expert-tips-for-tired-parents": [
        "conquering-sleep-battles-a-guide-for-parents-of-toddlers-who-fight-sleep",
        "conquering-the-sleep-struggle-a-guide-for-parents-of-toddlers-who-fight-sleep",
        "conquering-the-toddler-sleep-battle-strategies-for-exhausted-parents",
        "conquering-the-toddler-sleep-struggle-tips-for-exhausted-parents",
        "taming-the-bedtime-dragon-strategies-for-parents-of-needy-toddlers",
        "navigating-toddler-sleep-struggles-strategies-for-peaceful-bedtimes",
        "the-struggle-is-real-navigating-sleep-battles-with-your-child",
    ],
    "navigating-the-4-month-sleep-regression-tips-for-new-parents": [
        "navigating-the-4-month-sleep-regression-and-beyond-when-your-baby-cries-constantly",
    ],
    "thoughtful-gift-ideas-for-your-child-s-parent-after-separation": [
        "thoughtful-gifts-for-your-child-s-other-parent-after-a-separation",
        "thoughtful-gifts-for-your-ex-from-your-child-navigating-post-separation-kindness",
    ],
    "the-importance-of-getting-young-children-out-of-the-house-addressing-differing-parental-views": [
        "the-importance-of-getting-young-children-out-of-the-house-weekly",
    ],
    "dad-s-guide-to-pregnancy-and-childbirth-essential-tips-for-expecting-fathers": [
        "dad-s-guide-to-navigating-pregnancy-and-childbirth",
        "dad-tips-for-expecting-parents-a-comprehensive-guide",
        "dad-tips-preparing-for-parenthood",
        "a-dad-s-guide-to-preparing-for-parenthood",
        "navigating-labor-day-a-new-dad-s-guide-to-supporting-your-partner-and-welcoming-your-son",
    ],
}

MERGE_LOOKUP = {}
for canonical, dupes in MERGE_GROUPS.items():
    for dupe in dupes:
        MERGE_LOOKUP[dupe] = canonical


def classify_article(slug, title, h1, meta_description, size):
    # 1. merge: curated near-duplicates (only if canonical is in KEEP_SLUGS)
    # Check this FIRST so merge stubs (which are small) aren't classified as remove
    if slug in MERGE_LOOKUP:
        canonical = MERGE_LOOKUP[slug]
        if canonical in KEEP_SLUGS:
            return ("merge", f"resources/{canonical}.html",
                    f"Near-duplicate; canonical: {canonical}")
        else:
            # Canonical not kept -> noindex this duplicate too
            return ("noindex", "", "Duplicate of off-audience canonical")

    # 0. remove: empty/broken only
    if not title or len(title) < 5 or size < 1500:
        return ("remove", "", "Empty or broken page (missing title or tiny file)")

    # 2. explicit keep list
    if slug in KEEP_SLUGS:
        return ("keep", "", "Explicitly curated core 0-3 article")

    # 3. everything else -> noindex
    return ("noindex", "", "Not in curated core 0-3 allowlist")


def main():
    base = Path(__file__).resolve().parent.parent
    resources_dir = base / "resources"
    seo_dir = base / "seo"
    seo_dir.mkdir(exist_ok=True)

    html_files = sorted(resources_dir.glob("*.html"))

    print(f"Found {len(html_files)} resource files")
    results = []
    for filepath in html_files:
        filename = filepath.name
        if filename == "index.html":
            continue
        slug = filename[:-5]
        parsed = parse_html_file(filepath)
        decision, merge_target, reason = classify_article(
            slug, parsed["title"], parsed["h1"], parsed["meta_description"],
            parsed["size"],
        )
        results.append({
            "path": f"resources/{filename}",
            "title": parsed["title"],
            "decision": decision,
            "merge_target": merge_target,
            "reason": reason,
        })

    output_path = seo_dir / "classification.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["path", "title", "decision", "merge_target", "reason"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"Classification complete: {output_path}")
    counts = {}
    for r in results:
        counts[r["decision"]] = counts.get(r["decision"], 0) + 1
    print(f"Summary: {counts}")

    # Show keep articles
    keeps = [r for r in results if r["decision"] == "keep"]
    print(f"\nKEEP articles ({len(keeps)}):")
    for r in keeps:
        print(f"  {r['path']} - {r['title'][:80]}")


if __name__ == "__main__":
    main()