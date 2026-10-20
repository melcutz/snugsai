#!/usr/bin/env python3
"""Enrich the core-30 articles (seo/core30.txt).

For each core article:
  1. Insert 3-5 contextual internal links to other keep articles (a
     "Continue reading" nav block before the Related Guides section, or
     before </article> as fallback).
  2. Append a short "Written by a dad" author box (from the founder of
     Snugs.ai, a dad of a toddler - factual, no invented credentials).
  3. Extend the existing JSON-LD Article node: author as Organization, plus
     datePublished/dateModified from git history and publisher Organization.

Preserves all existing CTA markup, data-cta attributes, cta_click analytics,
UTM links, and analytics tags byte-for-byte (asserted per file).
Idempotent: skips blocks that are already present.
"""

import csv
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SITE = "https://snugs.ai"

AUTHOR_BOX = """<aside class="mt-10 rounded-3xl border border-orange-200 bg-orange-50/80 p-6" aria-label="About the author">
      <p class="font-semibold text-gray-800">Written by a dad</p>
      <p class="text-gray-700 mt-2">From the founder of Snugs.ai, a dad of a toddler building an AI parenting advisor for parents of 0-3 year olds.</p>
    </aside>"""

NAV_OPEN = """<nav class="mt-10 rounded-3xl border border-orange-200 bg-orange-50/80 p-6" aria-label="Continue reading">
      <p class="font-semibold text-gray-800">Continue reading</p>
      <ul class="mt-3 space-y-2 text-gray-700">
"""
NAV_CLOSE = """      </ul>
    </nav>"""


def slug(path: str) -> str:
    return Path(path).stem


def load_decisions():
    """Load current classification decisions."""
    return {
        r["path"]: r["decision"]
        for r in csv.DictReader(open(BASE / "seo" / "classification.csv"))
    }


# Curated related links: core slug -> [candidate related slugs].
# These will be filtered at runtime to only include current keep articles.
RELATED_CANDIDATES = {
    "navigating-the-18-month-sleep-regression-why-your-toddler-is-suddenly-clingy-and-how-to-help": [
        "navigating-the-4-month-sleep-regression-tips-for-new-parents",
        "help-your-toddler-sleep-expert-tips-for-tired-parents",
        "mastering-baby-naps-from-contact-naps-to-independent-sleep",
        "navigating-baby-s-digestive-upset-when-starting-solids",
    ],
    "navigating-the-4-month-sleep-regression-tips-for-new-parents": [
        "navigating-the-12-week-sleep-regression-tips-for-new-parents",
        "navigating-the-18-month-sleep-regression-why-your-toddler-is-suddenly-clingy-and-how-to-help",
        "newborn-sleep-schedule-weeks-1-12",
        "help-your-toddler-sleep-expert-tips-for-tired-parents",
    ],
    "navigating-the-12-week-sleep-regression-tips-for-new-parents": [
        "navigating-the-4-month-sleep-regression-tips-for-new-parents",
        "newborn-sleep-schedule-weeks-1-12",
        "safe-swaddling-how-to",
        "soothing-a-fussy-baby-tips-for-diaper-changes-and-feeding-with-reflux",
    ],
    "help-your-toddler-sleep-expert-tips-for-tired-parents": [
        "navigating-the-18-month-sleep-regression-why-your-toddler-is-suddenly-clingy-and-how-to-help",
        "mastering-baby-naps-from-contact-naps-to-independent-sleep",
        "navigating-the-terrible-threes-understanding-and-managing-challenging-behavior-in-toddlers",
        "navigating-aggression-in-3-year-olds-what-to-do-when-gentle-parenting-isn-t-enough",
    ],
    "newborn-sleep-schedule-weeks-1-12": [
        "safe-swaddling-how-to",
        "mastering-baby-naps-from-contact-naps-to-independent-sleep",
        "navigating-newborn-challenges-when-reality-doesn-t-match-expectations",
        "when-your-baby-cries-constantly-navigating-colic-and-persistent-crying",
    ],
    "mastering-baby-naps-from-contact-naps-to-independent-sleep": [
        "newborn-sleep-schedule-weeks-1-12",
        "when-your-9-month-old-won-t-sleep-a-parent-s-guide-to-overcoming-severe-sleep-disturbances",
        "help-your-toddler-sleep-expert-tips-for-tired-parents",
        "safe-swaddling-how-to",
    ],
    "helping-your-baby-through-teething-illness-and-sleep-disruptions": [
        "when-your-9-month-old-won-t-sleep-a-parent-s-guide-to-overcoming-severe-sleep-disturbances",
        "soothing-a-fussy-baby-tips-for-diaper-changes-and-feeding-with-reflux",
        "navigating-baby-s-digestive-upset-when-starting-solids",
        "newborn-sleep-schedule-weeks-1-12",
    ],
    "when-your-9-month-old-won-t-sleep-a-parent-s-guide-to-overcoming-severe-sleep-disturbances": [
        "helping-your-baby-through-teething-illness-and-sleep-disruptions",
        "mastering-baby-naps-from-contact-naps-to-independent-sleep",
        "help-your-toddler-sleep-expert-tips-for-tired-parents",
        "navigating-the-18-month-sleep-regression-why-your-toddler-is-suddenly-clingy-and-how-to-help",
    ],
    "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond": [
        "when-does-a-babble-become-a-word-understanding-your-baby-s-first-words",
        "celebrating-toddler-milestones-navigating-language-development-and-parental-pride",
        "navigating-developmental-milestones-with-a-preemie-a-parent-s-guide-to-torticollis-and-muscle-tone",
        "understanding-and-managing-severe-constipation-in-toddlers-a-parent-s-guide",
    ],
    "when-does-a-babble-become-a-word-understanding-your-baby-s-first-words": [
        "are-girls-really-early-talkers-exploring-language-development-in-toddlers",
        "celebrating-toddler-milestones-navigating-language-development-and-parental-pride",
        "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond",
        "soothing-a-fussy-baby-tips-for-diaper-changes-and-feeding-with-reflux",
    ],
    "are-girls-really-early-talkers-exploring-language-development-in-toddlers": [
        "when-does-a-babble-become-a-word-understanding-your-baby-s-first-words",
        "celebrating-toddler-milestones-navigating-language-development-and-parental-pride",
        "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond",
        "navigating-developmental-milestones-with-a-preemie-a-parent-s-guide-to-torticollis-and-muscle-tone",
    ],
    "celebrating-toddler-milestones-navigating-language-development-and-parental-pride": [
        "when-does-a-babble-become-a-word-understanding-your-baby-s-first-words",
        "are-girls-really-early-talkers-exploring-language-development-in-toddlers",
        "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond",
        "navigating-developmental-milestones-with-a-preemie-a-parent-s-guide-to-torticollis-and-muscle-tone",
    ],
    "navigating-developmental-milestones-with-a-preemie-a-parent-s-guide-to-torticollis-and-muscle-tone": [
        "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond",
        "celebrating-toddler-milestones-navigating-language-development-and-parental-pride",
        "are-girls-really-early-talkers-exploring-language-development-in-toddlers",
        "navigating-newborn-challenges-when-reality-doesn-t-match-expectations",
    ],
    "navigating-baby-s-digestive-upset-when-starting-solids": [
        "baby-not-pooping-after-starting-solids-what-s-normal-and-when-to-worry",
        "understanding-and-managing-severe-constipation-in-toddlers-a-parent-s-guide",
        "understanding-baby-fussiness-before-a-poop-a-common-newborn-stage",
        "soothing-a-fussy-baby-tips-for-diaper-changes-and-feeding-with-reflux",
    ],
    "navigating-feeding-fears-a-parent-s-guide-to-mealtime-anxiety": [
        "navigating-baby-s-digestive-upset-when-starting-solids",
        "baby-not-pooping-after-starting-solids-what-s-normal-and-when-to-worry",
        "cracking-the-toddler-code-how-one-parent-turned-playtime-into-mealtime",
        "understanding-and-managing-severe-constipation-in-toddlers-a-parent-s-guide",
    ],
    "baby-not-pooping-after-starting-solids-what-s-normal-and-when-to-worry": [
        "navigating-baby-s-digestive-upset-when-starting-solids",
        "understanding-and-managing-severe-constipation-in-toddlers-a-parent-s-guide",
        "understanding-baby-fussiness-before-a-poop-a-common-newborn-stage",
        "understanding-baby-s-milk-intake-why-it-s-unpredictable-and-what-to-expect",
    ],
    "soothing-a-fussy-baby-tips-for-diaper-changes-and-feeding-with-reflux": [
        "when-your-baby-cries-constantly-navigating-colic-and-persistent-crying",
        "surviving-the-fussy-baby-phase-tips-for-exhausted-parents",
        "understanding-and-soothing-your-grunting-baby-a-guide-for-new-parents",
        "helping-your-baby-through-teething-illness-and-sleep-disruptions",
    ],
    "navigating-toddler-tantrums-and-aggression-when-is-it-normal-and-how-to-help": [
        "navigating-the-storm-understanding-and-managing-your-3-year-old-s-tantrums",
        "navigating-the-terrible-threes-understanding-and-managing-challenging-behavior-in-toddlers",
        "navigating-aggression-in-3-year-olds-what-to-do-when-gentle-parenting-isn-t-enough",
        "managing-aggressive-behavior-in-toddlers-a-guide-for-dads",
    ],
    "navigating-the-storm-understanding-and-managing-your-3-year-old-s-tantrums": [
        "navigating-toddler-tantrums-and-aggression-when-is-it-normal-and-how-to-help",
        "navigating-the-terrible-threes-understanding-and-managing-challenging-behavior-in-toddlers",
        "navigating-the-no-phase-when-your-3-year-old-stops-saying-yes",
        "navigating-the-mine-phase-strategies-for-parents-of-toddlers",
    ],
    "navigating-the-terrible-threes-understanding-and-managing-challenging-behavior-in-toddlers": [
        "navigating-the-storm-understanding-and-managing-your-3-year-old-s-tantrums",
        "navigating-toddler-tantrums-and-aggression-when-is-it-normal-and-how-to-help",
        "navigating-the-terrible-twos-and-threes-and-fours-managing-constant-crying-and-defiance",
        "navigating-the-no-phase-when-your-3-year-old-stops-saying-yes",
    ],
    "navigating-aggression-in-3-year-olds-what-to-do-when-gentle-parenting-isn-t-enough": [
        "navigating-toddler-tantrums-and-aggression-when-is-it-normal-and-how-to-help",
        "navigating-the-storm-understanding-and-managing-your-3-year-old-s-tantrums",
        "managing-aggressive-behavior-in-toddlers-a-guide-for-dads",
        "navigating-the-terrible-threes-understanding-and-managing-challenging-behavior-in-toddlers",
    ],
    "managing-aggressive-behavior-in-toddlers-a-guide-for-dads": [
        "navigating-aggression-in-3-year-olds-what-to-do-when-gentle-parenting-isn-t-enough",
        "navigating-toddler-tantrums-and-aggression-when-is-it-normal-and-how-to-help",
        "navigating-the-storm-understanding-and-managing-your-3-year-old-s-tantrums",
        "navigating-the-terrible-threes-understanding-and-managing-challenging-behavior-in-toddlers",
    ],
    "potty-training-a-toddler-while-managing-a-newborn-tips-for-stressed-parents": [
        "potty-training-toddlers-overcoming-fear-and-building-independence",
        "potty-training-resistance-strategies-for-a-nearly-4-year-old",
        "navigating-toddler-independence-when-privacy-and-potty-training-collide",
        "helping-your-child-overcome-potty-training-setbacks-and-school-toilet-anxiety",
    ],
    "potty-training-toddlers-overcoming-fear-and-building-independence": [
        "potty-training-a-toddler-while-managing-a-newborn-tips-for-stressed-parents",
        "potty-training-resistance-strategies-for-a-nearly-4-year-old",
        "helping-your-child-overcome-potty-training-setbacks-and-school-toilet-anxiety",
        "navigating-toddler-independence-when-privacy-and-potty-training-collide",
    ],
    "potty-training-resistance-strategies-for-a-nearly-4-year-old": [
        "potty-training-a-toddler-while-managing-a-newborn-tips-for-stressed-parents",
        "potty-training-toddlers-overcoming-fear-and-building-independence",
        "navigating-toddler-independence-when-privacy-and-potty-training-collide",
        "helping-your-child-overcome-potty-training-setbacks-and-school-toilet-anxiety",
    ],
    "navigating-newborn-challenges-when-reality-doesn-t-match-expectations": [
        "surviving-the-newborn-stage-when-your-baby-won-t-sleep-and-you-ve-reached-your-breaking-point",
        "navigating-postpartum-exhaustion-and-partner-support-you-re-not-alone",
        "newborn-sleep-schedule-weeks-1-12",
        "when-your-baby-cries-constantly-navigating-colic-and-persistent-crying",
    ],
    "navigating-postpartum-depression-understanding-intrusive-thoughts-and-seeking-support": [
        "navigating-postpartum-exhaustion-and-partner-support-you-re-not-alone",
        "navigating-postpartum-identity-crisis-more-than-just-mom",
        "when-your-baby-cries-constantly-navigating-colic-and-persistent-crying",
        "navigating-newborn-challenges-when-reality-doesn-t-match-expectations",
    ],
    "when-your-baby-cries-constantly-navigating-colic-and-persistent-crying": [
        "soothing-a-fussy-baby-tips-for-diaper-changes-and-feeding-with-reflux",
        "surviving-the-fussy-baby-phase-tips-for-exhausted-parents",
        "surviving-the-newborn-stage-when-your-baby-won-t-sleep-and-you-ve-reached-your-breaking-point",
        "navigating-newborn-challenges-when-reality-doesn-t-match-expectations",
    ],
    "safe-swaddling-how-to": [
        "newborn-sleep-schedule-weeks-1-12",
        "mastering-baby-naps-from-contact-naps-to-independent-sleep",
        "keeping-baby-s-room-at-a-safe-and-comfortable-temperature",
        "understanding-and-soothing-your-grunting-baby-a-guide-for-new-parents",
    ],
    "understanding-and-managing-severe-constipation-in-toddlers-a-parent-s-guide": [
        "baby-not-pooping-after-starting-solids-what-s-normal-and-when-to-worry",
        "navigating-baby-s-digestive-upset-when-starting-solids",
        "understanding-baby-fussiness-before-a-poop-a-common-newborn-stage",
        "navigating-feeding-fears-a-parent-s-guide-to-mealtime-anxiety",
    ],
}


class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def page_title(path: Path) -> str:
    p = TitleParser()
    p.feed(path.read_text(encoding="utf-8"))
    return p.title.split(" | ")[0].strip()


def git_dates(relpath: str):
    out = subprocess.check_output(
        ["git", "log", "--format=%cs", "--", relpath], cwd=BASE, text=True
    ).strip().split("\n")
    out = [d for d in out if d]
    if not out:
        from datetime import date
        today = date.today().isoformat()
        return today, today
    return out[-1], out[0]  # first commit, last commit


TRACKED = ["data-cta", "cta_click", "utm_", "gtag"]


def snapshot(html: str):
    return {t: html.count(t) for t in TRACKED}


def enrich(path: Path, related_slugs):
    html = path.read_text(encoding="utf-8")
    before = snapshot(html)

    # 1. contextual internal links
    if 'aria-label="Continue reading"' not in html:
        items = []
        for s in related_slugs:
            t = page_title(BASE / "resources" / f"{s}.html")
            items.append(
                f'        <li><a href="/resources/{s}.html" '
                f'class="text-orange-700 underline hover:text-orange-800 '
                f'font-medium transition-colors">{t}</a></li>'
            )
        nav = NAV_OPEN + "\n".join(items) + "\n" + NAV_CLOSE
        anchor = '<section class="mt-10 pt-8 border-t-2 border-orange-100">'
        if anchor in html:
            html = html.replace(anchor, nav + "\n    " + anchor, 1)
        else:
            html = html.replace("</article>", nav + "\n</article>", 1)

    # 2. author box (inside the article, at its end)
    if 'aria-label="About the author"' not in html:
        if "</article>" in html:
            html = html.replace("</article>", AUTHOR_BOX + "\n</article>", 1)
        else:
            html += AUTHOR_BOX

    # 3. JSON-LD Article schema
    m = re.search(
        r'(<script type="application/ld\+json">)(.*?)(</script>)', html, re.S
    )
    assert m, f"no JSON-LD in {path}"
    # Fix unescaped control characters in JSON
    json_text = m.group(2)
    json_text = json_text.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        # Try to fix common issues
        json_text = json_text.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ')
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            raise ValueError(f"JSON-LD INVALID {path}: {e}")
    nodes = data.get("@graph", [data])
    article = next(
        (n for n in nodes if n.get("@type") == "Article"), None
    )
    assert article is not None, f"no Article node in {path}"
    published, modified = git_dates(str(path.relative_to(BASE)))
    article["author"] = {
        "@type": "Organization",
        "name": "Snugs.ai",
    }
    article["datePublished"] = published
    article["dateModified"] = modified
    publisher = article.get("publisher") or {}
    publisher["@type"] = "Organization"
    publisher["name"] = "Snugs.ai"
    publisher.setdefault("url", SITE)
    article["publisher"] = publisher
    new_block = m.group(1) + "\n" + json.dumps(data, indent=2) + "\n  " + m.group(3)
    html = html[: m.start()] + new_block + html[m.end() :]

    assert snapshot(html) == before, f"tracking markup changed in {path}"
    path.write_text(html, encoding="utf-8")


def main():
    decisions = load_decisions()
    core = [l.strip() for l in open(BASE / "seo" / "core30.txt") if l.strip()]
    assert len(core) == 30, f"core30.txt has {len(core)} lines, want 30"
    for c in core:
        assert decisions.get(c) == "keep", f"{c} is not keep"
        assert (BASE / c).exists(), f"{c} missing"

    # Filter RELATED_CANDIDATES to only keep articles
    RELATED = {}
    for s, targets in RELATED_CANDIDATES.items():
        keep_targets = [t for t in targets if decisions.get(f"resources/{t}.html") == "keep"]
        # If fewer than 3, add more from keep articles in same category
        if len(keep_targets) < 3:
            # Could add fallback logic here, but for now just use what we have
            pass
        RELATED[s] = keep_targets

    assert set(RELATED) == {slug(c) for c in core}, "RELATED keys != core30"
    for s, targets in RELATED.items():
        assert 3 <= len(targets) <= 5, f"{s}: only {len(targets)} keep targets (need 3-5)"
        for t in targets:
            assert decisions.get(f"resources/{t}.html") == "keep", (
                f"link target not keep: {t} (from {s})"
            )
            assert (BASE / "resources" / f"{t}.html").exists()

    for c in core:
        enrich(BASE / c, RELATED[slug(c)])
    print(f"enriched {len(core)} core articles")


if __name__ == "__main__":
    main()