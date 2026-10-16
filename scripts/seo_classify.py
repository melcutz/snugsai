#!/usr/bin/env python3
"""SEO classification for Snugs.ai resources.

Reads every resources/*.html (title, h1, meta description) and produces
seo/classification.csv with columns: path,title,decision,merge_target,reason.

Audience rule:
  keep    = pregnancy, newborn, baby and toddler (roughly 0-3 years) parenting
            topics, and general dad/parent topics that clearly serve parents of
            young kids.
  noindex = off-audience (dating profiles/romance unrelated to parenting,
            adult supplements/product comparisons, teens, adult children,
            in-laws of grown kids, school-age-only topics, non-parenting topics).
  merge   = near-duplicate articles on the same core topic (strongest kept as
            merge_target).
  remove  = empty/broken pages only. Conservative: prefer noindex over remove.

Order of checks (important):
  1. remove (empty/broken)
  2. explicit merge list (curated near-duplicates)
  3. CORE allowlist (regex, word boundaries) -> keep. Checked BEFORE noindex so
     core 0-3 topics (sleep training, lullabies, swaddling, baby poop, ...) are
     never flagged by an overlapping off-audience keyword.
  4. noindex patterns (regex with word boundaries - no naive substring
     matching, so "between" never matches "tween", "protein" never matches
     "teen", baby "supplementation" (formula) never matches adult supplements).
  5. default: keep (conservative - borderline general-parenting topics stay
     indexed; only clearly off-audience pages are noindexed).
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


# ----------------------------------------------------------------------------
# 0. PRE-check noindex: explicitly off-audience per issue #8 (dating profiles,
#    teen content, adult supplements, etc.). Checked BEFORE the core allowlist
#    because these pages often also mention "father"/"single parent".
# ----------------------------------------------------------------------------
PRE_NOINDEX_PATTERNS = [
    (r"\bdating\b", "dating content"),
    (r"dating profile", "dating profiles"),
    (r"finding love", "finding love after heartbreak"),
    (r"disclose.*children.*dat", "disclosing children on dating profiles"),
    (r"mentioning children.*dat", "mentioning children on dating profiles"),
    (r"adjust to your new relationship", "new romantic relationship"),
    (r"meeting.*your new partner", "new romantic partner"),
    (r"child.*new partner.*single parent", "new romantic partner"),
    (r"feelings when meeting a new partner", "new romantic partner"),
    (r"\bteen(s|age|ager)?\b", "teen topic"),
    (r"\btween\b", "tween topic"),
    (r"\bpre[-\s]?teen\b", "pre-teen topic"),
    (r"\badolescen", "adolescent topic"),
    (r"\b([6-9]|1[0-8])[-\s]?year[-\s]?old\b", "school-age/teen (6+)"),
    (r"\bag1\b", "AG1 supplement"),
    (r"\bgruns\b", "Gruns supplement"),
    (r"greens powder", "greens powder"),
    (r"protein powder", "protein powder"),
    (r"daughter'?s boyfriend", "daughter's boyfriend"),
    (r"son'?s girlfriend", "son's girlfriend"),
]

# ----------------------------------------------------------------------------
# 1. CORE allowlist: anything matching is unambiguously in-audience -> keep.
#    Checked BEFORE the (post) noindex patterns so core 0-3 topics (sleep
#    training, lullabies, swaddling, baby poop, ...) are never flagged by an
#    overlapping off-audience keyword.
# ----------------------------------------------------------------------------
CORE_PATTERNS = [
    # sleep (core 0-3)
    r"sleep regression", r"sleep training", r"contact naps?",
    r"night wak", r"bedtime", r"\bnap\b", r"naps\b", r"nap transition",
    r"self[-\s]?sooth", r"white noise", r"swaddl", r"lulla",
    r"co[-\s]?sleep", r"sleep schedule", r"sleep cues?", r"sleep stretch",
    r"sleep disruption", r"sleep struggle", r"sleep battle", r"toddler sleep",
    r"baby sleep", r"newborn sleep", r"sleep\b.*\bbaby\b", r"put.*to sleep",
    r"won'?t sleep", r"waking up every", r"overnight diaper",
    r"nighttime sleep", r"room sharing", r"sleep sack",
    # age markers 0-3
    r"newborn", r"\binfant\b", r"\bbab(y|ies)\b", r"toddler",
    r"month[-\s]?old", r"week[-\s]?old", r"months old", r"weeks old",
    r"[0123][-\s]?year[-\s]?old", r"one[-\s]?year", r"two[-\s]?year",
    r"three[-\s]?year", r"12[-\s]?month", r"18[-\s]?month", r"0[-\s]?3\b",
    r"0[-\s]?12\b", r"under (3|three)\b", r"two under",
    # feeding / digestion / diapers / potty
    r"breastfeed", r"\bformula\b", r"pumped milk", r"\bbottle\b",
    r"\bsolids\b", r"starting solids", r"weaning", r"picky eating",
    r"mealtime", r"milk intake", r"\breflux\b", r"\bpoop\b", r"pooping",
    r"constipation", r"\bdiaper\b", r"potty train", r"toilet train",
    r"pull[-\s]?up", r"teething",
    # behavior / development 0-3
    r"tantrum", r"meltdown", r"terrible twos?", r"terrible threes?",
    r"gentle parenting", r"\bdiscipline\b", r"\bdefian", r"aggressi",
    r"separation anxiety", r"\battachment\b", r"\bbonding\b", r"\bcolic\b",
    r"\bfussy\b", r"crying baby", r"cries constantly", r"grunting baby",
    r"high[-\s]?needs baby", r"\bmilestone\b", r"developmen", r"\bwalking\b",
    r"\btalking\b", r"\bspeech\b", r"\blanguage\b", r"\bbabble\b",
    r"first word", r"tummy time", r"\bsensory\b", r"motor skills?",
    r"reading to (your )?baby", r"screen time.*infant",
    r"\bpreschool", r"daycare", r"\bnanny\b", r"babysitter", r"childcare",
    # health / safety of babies
    r"pediatrician", r"\bvaccin", r"immuniz", r"flu shot", r"\brsv\b",
    r"\bfever\b", r"\bcold\b.*baby", r"baby.*\bcold\b", r"\billness\b",
    r"tooth decay", r"cavities in infants", r"\bdentist\b.*baby",
    r"bath safety", r"baby fell", r"car seat", r"childproof",
    r"babyproof", r"\bchoking\b", r"suffocation", r"room temperature",
    r"keeping.*baby.*warm", r"underarms", r"hair matting",
    # pregnancy / postpartum / new parents
    r"pregnan", r"expecting", r"prenatal", r"childbirth", r"\blabor\b",
    r"\bdelivery\b", r"postpartum", r"fourth trimester", r"new mom",
    r"new dad", r"new parent", r"new fatherhood", r"\bnicu\b",
    r"unplanned pregnancy", r"single motherhood", r"single mom",
    r"single dad", r"single parent", r"solo m[ou]ther", r"newborn phase",
    r"newborn stage", r"early days.*parent", r"second child",
    r"age gap", r"sibling.*(newborn|baby|toddler)", r"new baby",
    # dad / parenting life serving young-kid parents
    r"\bdad\b", r"\bfather", r"paternal", r"mom guilt",
    r"parental (exhaustion|burnout|overwhelm)", r"parenting styles?",
    r"co[-\s]?parenting.*(toddler|baby|newborn|young|new baby)",
    r"custody.*(toddler|baby|young|2-year|almost 2)",
    r"relationship.*new parents?", r"marital strain.*newborn",
    r"partner.*(newborn|postpartum|new parent)",
    r"grandparent.*(baby|toddler|newborn)",
    r"rehome.*dog.*child.*safety", r"dog.*child.*safety",
    r"funeral.*toddler", r"talking.*death.*young children",
]

# ----------------------------------------------------------------------------
# 2. Off-audience noindex patterns (regex, word boundaries). Only checked
#    AFTER the core allowlist, so e.g. "co-parenting with toddlers" keeps.
# ----------------------------------------------------------------------------
NOINDEX_PATTERNS = [
    # elementary / school-age only
    (r"\belementary school", "elementary school age"),
    (r"\bgraphic novels? for elementary", "elementary readers"),
    (r"classroom snack", "classroom snacks"),
    (r"school ipad", "school iPads"),
    (r"school night chaos", "school nights"),
    (r"school parent involvement", "school parent involvement"),
    (r"teacher gift", "teacher gifts"),
    (r"shaving\b.*daughter|daughter.*shav", "teaching teen daughter to shave"),
    (r"oral hygiene in teenagers", "teenagers"),
    (r"overnight stays.*14-year", "14-year-old sleepovers"),
    (r"emotional rollercoaster.*preteen", "preteen years"),
    (r"loneliness in marriage", "marriage loneliness (not young-kid focused)"),
    # adult children / grown families
    (r"adult child", "adult children"),
    (r"grown child", "grown children"),
    (r"grown kids", "grown kids"),
    (r"daughter'?s boyfriend", "daughter's boyfriend"),
    (r"son'?s girlfriend", "son's girlfriend"),
    (r"retirement\b.*adult child|adult child.*retirement",
     "adult children/retirement"),
    (r"financial gifts to adult children", "gifts to adult children"),
    (r"holidays with grown children", "grown children's in-laws"),
    (r"college kid moving back", "college kid moving home"),
    # adult supplements / insurance / investment content for adults
    (r"hospital indemnity insurance", "hospital indemnity insurance"),
    (r"529 account", "529 account"),
    # non-parenting / novelty topics
    (r"willy wonka bedroom", "novelty bedroom build"),
    (r"sludge metal", "sludge metal music"),
    (r"pocket knives?", "pocket knives"),
    (r"\btattoo", "tattoos"),
    (r"fbi raid", "FBI raid"),
    (r"virtual vendetta", "gaming vendetta"),
    (r"gaming threat", "gaming threats"),
    (r"\broomba\b", "robot vacuum"),
    (r"robot vacuum", "robot vacuum"),
    (r"target gift card.*sale|save on teacher gifts", "gift card sale"),
    (r"amazon delivery driver.*bonus", "delivery driver bonus"),
    (r"\broblox\b", "Roblox (older kids gaming)"),
    (r"8-bit christmas|rediscover the 80s", "nostalgia content"),
    (r"ultimate family fleet", "family fleet pets"),
    # money/assistance spam + misc off-topic (no young-kid angle)
    (r"christmas assistance", "christmas assistance programs"),
    (r"holiday assistance.*georgia|growing need for holiday assistance",
     "holiday assistance"),
    (r"financial hardship and christmas", "financial hardship christmas"),
    (r"government aid.*single parent", "government aid"),
    (r"house poverty", "house poverty"),
    (r"career change.*single parent", "career change"),
    (r"balancing extracurriculars", "extracurriculars (older kids)"),
    (r"single parenthood juggling", "extracurricular juggling"),
    (r"move overseas|international relocation", "international relocation"),
    (r"school principal", "school principal"),
    (r"teacher concern", "teacher concerns (preschool admin)"),
    (r"reading all day.*normal", "bookworm toddler reading-all-day (thin)"),
    (r"melissa.{0,4}doug", "toy brand investment piece"),
    (r"investing in melissa", "toy brand investment piece"),
]

# ----------------------------------------------------------------------------
# 3. Curated merge groups: canonical slug -> [duplicate slugs].
#    Canonical must exist and be classified keep.
# ----------------------------------------------------------------------------
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
}

MERGE_LOOKUP = {}
for canonical, dupes in MERGE_GROUPS.items():
    for dupe in dupes:
        MERGE_LOOKUP[dupe] = canonical


def classify_article(slug, title, h1, meta_description, size):
    text = f"{title} {h1} {meta_description}".lower()

    # 0. remove: empty/broken only
    if not title or len(title) < 5 or size < 1500:
        return ("remove", "", "Empty or broken page (missing title or tiny file)")

    # 1. merge: curated near-duplicates
    if slug in MERGE_LOOKUP:
        canonical = MERGE_LOOKUP[slug]
        return ("merge", f"resources/{canonical}.html",
                f"Near-duplicate; canonical: {canonical}")

    # 2. pre-check: explicitly off-audience (dating, teens, adult supplements)
    for pat, label in PRE_NOINDEX_PATTERNS:
        if re.search(pat, text):
            return ("noindex", "", f"Off-audience ({label}): /{pat}/")

    # 2. core allowlist -> keep (checked before noindex)
    for pat in CORE_PATTERNS:
        if re.search(pat, text):
            return ("keep", "", f"Core 0-3 parenting topic: /{pat}/")

    # 3. off-audience -> noindex
    for pat, label in NOINDEX_PATTERNS:
        if re.search(pat, text):
            return ("noindex", "", f"Off-audience ({label}): /{pat}/")

    # 4. conservative default
    return ("keep", "", "General parenting topic; no off-audience signal")


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


if __name__ == "__main__":
    main()
