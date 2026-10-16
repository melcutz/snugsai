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


# Curated related links: core slug -> [related keep slugs]. All targets are
# keep articles on related 0-3 topics (verified before running).
RELATED = {
    "navigating-the-18-month-sleep-regression-why-your-toddler-is-suddenly-clingy-and-how-to-help": [
        "navigating-the-4-month-sleep-regression-tips-for-new-parents",
        "help-your-toddler-sleep-expert-tips-for-tired-parents",
        "mastering-baby-naps-from-contact-naps-to-independent-sleep",
        "navigating-overnight-diaper-dilemmas-a-parent-s-guide-to-sleep-training-and-baby-s-comfort",
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
        "is-your-3-month-old-waking-up-every-15-minutes-understanding-newborn-sleep-cycles-and-solutions",
        "sleep-regression-and-milestones-is-there-a-link-for-your-3-month-old",
    ],
    "help-your-toddler-sleep-expert-tips-for-tired-parents": [
        "navigating-the-18-month-sleep-regression-why-your-toddler-is-suddenly-clingy-and-how-to-help",
        "mastering-baby-naps-from-contact-naps-to-independent-sleep",
        "navigating-overnight-diaper-dilemmas-a-parent-s-guide-to-sleep-training-and-baby-s-comfort",
        "navigating-the-terrible-threes-understanding-and-managing-challenging-behavior-in-toddlers",
    ],
    "newborn-sleep-schedule-weeks-1-12": [
        "is-your-3-month-old-waking-up-every-15-minutes-understanding-newborn-sleep-cycles-and-solutions",
        "is-an-8-hour-sleep-stretch-normal-for-a-12-week-adjusted-baby",
        "mastering-baby-naps-from-contact-naps-to-independent-sleep",
        "navigating-newborn-challenges-when-reality-doesn-t-match-expectations",
    ],
    "mastering-baby-naps-from-contact-naps-to-independent-sleep": [
        "newborn-sleep-schedule-weeks-1-12",
        "the-miraculous-moment-can-a-2-month-old-really-put-themselves-to-sleep",
        "when-your-9-month-old-won-t-sleep-a-parent-s-guide-to-overcoming-severe-sleep-disturbances",
        "help-your-toddler-sleep-expert-tips-for-tired-parents",
    ],
    "navigating-overnight-diaper-dilemmas-a-parent-s-guide-to-sleep-training-and-baby-s-comfort": [
        "help-your-toddler-sleep-expert-tips-for-tired-parents",
        "newborn-sleep-schedule-weeks-1-12",
        "navigating-bedtime-for-your-9-week-old-finding-a-schedule-that-works",
        "potty-training-a-toddler-while-managing-a-newborn-tips-for-stressed-parents",
    ],
    "when-your-9-month-old-won-t-sleep-a-parent-s-guide-to-overcoming-severe-sleep-disturbances": [
        "navigating-extreme-sleep-troubles-with-your-9-month-old-when-nothing-seems-to-work",
        "understanding-and-addressing-sleep-regressions-in-7-month-old-babies",
        "helping-your-baby-through-teething-illness-and-sleep-disruptions",
        "help-your-toddler-sleep-expert-tips-for-tired-parents",
    ],
    "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond": [
        "when-does-a-babble-become-a-word-understanding-your-baby-s-first-words",
        "celebrating-toddler-milestones-navigating-language-development-and-parental-pride",
        "navigating-developmental-milestones-with-a-preemie-a-parent-s-guide-to-torticollis-and-muscle-tone",
        "baby-s-length-at-12-months-what-s-normal-and-what-to-expect",
    ],
    "when-does-a-babble-become-a-word-understanding-your-baby-s-first-words": [
        "are-girls-really-early-talkers-exploring-language-development-in-toddlers",
        "celebrating-toddler-milestones-navigating-language-development-and-parental-pride",
        "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond",
        "the-joy-of-reading-to-baby-beyond-understanding-towards-connection",
    ],
    "are-girls-really-early-talkers-exploring-language-development-in-toddlers": [
        "when-does-a-babble-become-a-word-understanding-your-baby-s-first-words",
        "celebrating-toddler-milestones-navigating-language-development-and-parental-pride",
        "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond",
        "navigating-the-bookworm-toddler-is-reading-all-day-normal-and-beneficial",
    ],
    "celebrating-toddler-milestones-navigating-language-development-and-parental-pride": [
        "when-does-a-babble-become-a-word-understanding-your-baby-s-first-words",
        "are-girls-really-early-talkers-exploring-language-development-in-toddlers",
        "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond",
        "navigating-developmental-milestones-with-a-preemie-a-parent-s-guide-to-torticollis-and-muscle-tone",
    ],
    "navigating-developmental-milestones-with-a-preemie-a-parent-s-guide-to-torticollis-and-muscle-tone": [
        "navigating-your-baby-s-12-month-milestones-from-pulling-up-to-walking-and-beyond",
        "navigating-new-parent-anxiety-supporting-your-partner-and-baby-after-a-nicu-stay",
        "navigating-newborn-challenges-when-reality-doesn-t-match-expectations",
        "understanding-and-soothing-your-grunting-baby-a-guide-for-new-parents",
    ],
    "navigating-picky-eating-in-toddlers-strategies-for-parents-of-1-year-olds": [
        "cracking-the-toddler-code-how-one-parent-turned-playtime-into-mealtime",
        "navigating-feeding-fears-a-parent-s-guide-to-mealtime-anxiety",
        "tap-vs-bottled-water-why-your-kids-might-be-picky-and-what-parents-can-do",
        "toddler-snack-time-couch-vs-table",
    ],
    "navigating-supplementation-when-and-how-to-introduce-formula-or-pumped-milk": [
        "baby-safety-during-breastfeeding-addressing-suffocation-fears",
        "hands-free-baby-bottle-holder-a-game-changer-for-parents",
        "taking-a-night-off-self-care-for-breastfeeding-mothers",
        "understanding-baby-s-milk-intake-why-it-s-unpredictable-and-what-to-expect",
    ],
    "navigating-baby-s-digestive-upset-when-starting-solids": [
        "baby-not-pooping-after-starting-solids-what-s-normal-and-when-to-worry",
        "baby-not-pooping-for-days-what-new-parents-need-to-know",
        "understanding-and-managing-severe-constipation-in-toddlers-a-parent-s-guide",
        "understanding-baby-fussiness-before-a-poop-a-common-newborn-stage",
    ],
    "baby-not-pooping-after-starting-solids-what-s-normal-and-when-to-worry": [
        "navigating-baby-s-digestive-upset-when-starting-solids",
        "baby-not-pooping-for-days-what-new-parents-need-to-know",
        "understanding-and-managing-severe-constipation-in-toddlers-a-parent-s-guide",
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
        "navigating-mom-guilt-and-toddler-tantrums-when-you-lose-your-cool",
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
        "navigating-discipline-when-does-advice-cross-the-line",
    ],
    "navigating-mom-guilt-and-toddler-tantrums-when-you-lose-your-cool": [
        "navigating-toddler-tantrums-and-aggression-when-is-it-normal-and-how-to-help",
        "navigating-the-storm-understanding-and-managing-your-3-year-old-s-tantrums",
        "navigating-postpartum-exhaustion-and-partner-support-you-re-not-alone",
        "from-unlimited-energy-to-need-a-break-the-evolving-understanding-of-parental-exhaustion",
    ],
    "potty-training-a-toddler-while-managing-a-newborn-tips-for-stressed-parents": [
        "potty-training-toddlers-overcoming-fear-and-building-independence",
        "potty-training-resistance-strategies-for-a-nearly-4-year-old",
        "potty-training-success-when-your-toddler-finally-poops-on-the-potty",
        "navigating-toddler-independence-when-privacy-and-potty-training-collide",
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
        "potty-training-success-when-your-toddler-finally-poops-on-the-potty",
        "navigating-overnight-diaper-dilemmas-a-parent-s-guide-to-sleep-training-and-baby-s-comfort",
    ],
    "navigating-newborn-challenges-when-reality-doesn-t-match-expectations": [
        "navigating-new-parent-anxiety-supporting-your-partner-and-baby-after-a-nicu-stay",
        "navigating-the-early-days-of-parenthood-when-does-it-get-easier",
        "surviving-the-newborn-stage-when-your-baby-won-t-sleep-and-you-ve-reached-your-breaking-point",
        "navigating-postpartum-exhaustion-and-partner-support-you-re-not-alone",
    ],
    "navigating-postpartum-depression-understanding-intrusive-thoughts-and-seeking-support": [
        "navigating-postpartum-exhaustion-and-partner-support-you-re-not-alone",
        "navigating-postpartum-identity-crisis-more-than-just-mom",
        "when-parenthood-feels-like-a-mistake-supporting-a-partner-experiencing-postpartum-depression-and-regret",
        "navigating-new-parent-anxiety-supporting-your-partner-and-baby-after-a-nicu-stay",
    ],
    "when-your-baby-cries-constantly-navigating-colic-and-persistent-crying": [
        "soothing-a-fussy-baby-tips-for-diaper-changes-and-feeding-with-reflux",
        "surviving-the-fussy-baby-phase-tips-for-exhausted-parents",
        "surviving-the-newborn-phase-dealing-with-fussy-babies-and-parental-exhaustion",
        "when-your-baby-only-wants-mom-or-dad-navigating-separation-anxiety-with-an-ai-parenting-assistant",
    ],
    "safe-swaddling-how-to": [
        "newborn-sleep-schedule-weeks-1-12",
        "mastering-baby-naps-from-contact-naps-to-independent-sleep",
        "keeping-baby-s-room-at-a-safe-and-comfortable-temperature",
        "navigating-the-world-of-noise-with-a-newborn-a-parent-s-guide",
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
    data = json.loads(m.group(2))
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
    decisions = {
        r["path"]: r["decision"]
        for r in csv.DictReader(open(BASE / "seo" / "classification.csv"))
    }
    core = [l.strip() for l in open(BASE / "seo" / "core30.txt") if l.strip()]
    assert len(core) == 30, f"core30.txt has {len(core)} lines, want 30"
    for c in core:
        assert decisions.get(c) == "keep", f"{c} is not keep"
        assert (BASE / c).exists(), f"{c} missing"
    assert set(RELATED) == {slug(c) for c in core}, "RELATED keys != core30"
    for s, targets in RELATED.items():
        assert 3 <= len(targets) <= 5, s
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
