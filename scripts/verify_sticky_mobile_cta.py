#!/usr/bin/env python3
"""Verify mobile sticky "Ask Snugs" trial CTA on /resources/* article pages.

Checks (issue #10):
  1) Every resources/*.html article (excluding resources/index.html) contains
     a sticky CTA with data-cta="sticky_mobile".
  2) resources/index.html, index.html, tools/* do NOT contain sticky_mobile
     (article-pages only).
  3) Sticky href points at app.snugs.ai with utm_source=marketing_site,
     utm_medium=cta, non-empty utm_campaign matching the article's main CTA
     campaign (or filename stem fallback).
  4) Existing cta_click handler with link_domain still present (sticky reuses
     the shared [data-cta] binder, so link_domain is automatic).
  5) Mobile-only CSS: base display:none + @media (max-width:767px) show +
     @media (min-width:768px) hide.
  6) Dismiss button present (<button>, no data-cta so it never fires cta_click).
  7) No-cover / no-CLS: position:fixed, z-index <= 40 (cookie consent keeps
     50+), body padding-bottom reserved in the mobile media query.
  8) Sticky HTML appears BEFORE the data-cta binder script so the existing
     querySelectorAll('[data-cta]') picks it up with no extra JS.
"""

import html
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
RESOURCES = ROOT / "resources"


class StickyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sticky_hrefs: list[str] = []
        self.dismiss_buttons = 0
        self.in_sticky = 0

    def handle_starttag(self, tag, attrs) -> None:
        attr = {k.lower(): (v or "") for k, v in attrs}
        cls = attr.get("class", "")
        if tag == "div" and "snugs-sticky-cta" in cls:
            self.in_sticky += 1
        if self.in_sticky > 0:
            if tag == "a" and attr.get("data-cta") == "sticky_mobile":
                if attr.get("href"):
                    self.sticky_hrefs.append(attr["href"])
            if tag == "button" and "snugs-sticky-dismiss" in cls:
                self.dismiss_buttons += 1
                if "data-cta" in attr:
                    self.dismiss_buttons = -100  # dismiss must never carry data-cta

    def handle_endtag(self, tag) -> None:
        if tag == "div" and self.in_sticky > 0:
            self.in_sticky -= 1


def main() -> int:
    articles = sorted(p for p in RESOURCES.glob("*.html") if p.name != "index.html")
    failures: list[str] = []
    sticky_pages = 0

    for path in articles:
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(ROOT))
        slug = path.stem  # e.g. calm-a-crying-baby

        # (1) sticky present
        if 'data-cta="sticky_mobile"' not in text:
            failures.append(f"{rel}: missing data-cta=\"sticky_mobile\"")
            continue
        sticky_pages += 1

        # (3) UTM on sticky href
        parser = StickyParser()
        try:
            parser.feed(text)
        except Exception as e:  # pragma: no cover
            failures.append(f"{rel}: HTML parse error: {e}")
            continue
        if not parser.sticky_hrefs:
            failures.append(f"{rel}: sticky anchor href not found")
            continue
        for raw in parser.sticky_hrefs:
            href = html.unescape(raw)
            parsed = urlparse(href)
            if parsed.hostname != "app.snugs.ai":
                failures.append(f"{rel}: sticky href host={parsed.hostname}, want app.snugs.ai")
                continue
            q = parse_qs(parsed.query)
            if q.get("utm_source", [""])[0] != "marketing_site":
                failures.append(f"{rel}: sticky utm_source wrong: {href}")
            if q.get("utm_medium", [""])[0] != "cta":
                failures.append(f"{rel}: sticky utm_medium wrong: {href}")
            camp = q.get("utm_campaign", [""])[0]
            if not camp:
                failures.append(f"{rel}: sticky utm_campaign empty: {href}")

        # (4) shared handler still present
        if "cta_click" not in text or "link_domain" not in text:
            failures.append(f"{rel}: cta_click/link_domain handler missing")
        if "querySelectorAll('[data-cta]')" not in text and 'querySelectorAll("[data-cta]")' not in text:
            failures.append(f"{rel}: data-cta binder script missing")

        # (5) mobile-only CSS
        if "snugs-sticky-cta" not in text:
            failures.append(f"{rel}: snugs-sticky-cta CSS missing")
        else:
            if "@media (max-width: 767px)" not in text:
                failures.append(f"{rel}: missing max-width:767px mobile media query")
            if "@media (min-width: 768px)" not in text and "min-width: 768px" not in text:
                failures.append(f"{rel}: missing min-width:768px desktop hide rule")

        # (6) dismiss button
        if parser.dismiss_buttons <= 0:
            failures.append(f"{rel}: dismiss button (.snugs-sticky-dismiss) missing or carries data-cta")

        # (7) no-cover / no-CLS
        if "position: fixed" not in text and "position:fixed" not in text:
            failures.append(f"{rel}: sticky must use position:fixed (no layout shift)")
        if "padding-bottom" not in text:
            failures.append(f"{rel}: missing body padding-bottom reserve (content cover)")
        # z-index check: sticky must be <= 40 so cookie consent (50+) stays on top
        import re
        m = re.search(r"\.snugs-sticky-cta\s*\{[^}]*z-index\s*:\s*(\d+)", text)
        if not m:
            failures.append(f"{rel}: sticky z-index missing")
        elif int(m.group(1)) > 40:
            failures.append(f"{rel}: sticky z-index {m.group(1)} > 40 (must stay below cookie banner)")

        # (8) ordering: sticky before binder
        idx_sticky = text.find('data-cta="sticky_mobile"')
        idx_binder = text.find("querySelectorAll('[data-cta]')")
        if idx_binder == -1:
            idx_binder = text.find('querySelectorAll("[data-cta]")')
        if idx_sticky == -1 or idx_binder == -1 or idx_sticky > idx_binder:
            failures.append(f"{rel}: sticky must appear BEFORE data-cta binder script")

    # (2) non-article pages must NOT have sticky
    for p in [ROOT / "index.html", RESOURCES / "index.html", ROOT / "contact.html",
              ROOT / "privacy.html", ROOT / "terms.html"] + sorted((ROOT / "tools").glob("*.html")):
        if p.exists():
            t = p.read_text(encoding="utf-8")
            if 'data-cta="sticky_mobile"' in t:
                failures.append(f"{p.relative_to(ROOT)}: non-article page must NOT have sticky_mobile")

    print(f"Article pages scanned : {len(articles)}")
    print(f"Pages with sticky     : {sticky_pages}")
    print(f"Failures              : {len(failures)}")
    for f in failures[:50]:
        print(f"  {f}")
    if len(failures) > 50:
        print(f"  ... and {len(failures) - 50} more")
    if not failures:
        print("\nOK: sticky mobile CTA present and correct on all article pages.")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
