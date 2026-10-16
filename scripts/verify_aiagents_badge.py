#!/usr/bin/env python3
"""Verify the AI Agents Directory "Featured on" badge in every page footer.

Checks (issue #14):
  1) Every .html file with a <footer> element contains exactly ONE
     data-badge="aiagentsdirectory" element (og/brand/templates/* email
     templates are exempt).
  2) The badge is located INSIDE the footer element (between <footer ...>
     and its closing </footer>).
  3) The badge <a> href starts with https://aiagentsdirectory.com/agent/snugsai,
     opens in a new tab (target="_blank") and rel contains "noopener".
  4) The badge <img> src is https://aiagentsdirectory.com/featured-badge.svg?v=2024
     with width=200 and height=50.
Footerless meta-refresh redirect stubs in resources/ and pages without a
footer are not part of the badge surface, so they are not checked.
"""

import html
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIR = ROOT / "og" / "brand" / "templates"

BADGE_MARK = 'data-badge="aiagentsdirectory"'
WANTED_HREF_PREFIX = "https://aiagentsdirectory.com/agent/snugsai"
WANTED_IMG_SRC = "https://aiagentsdirectory.com/featured-badge.svg?v=2024"
WANTED_WIDTH = "200"
WANTED_HEIGHT = "50"


def is_merge_stub(text: str) -> bool:
    """Footerless meta-refresh redirect stubs have no footer surface: exempt."""
    return 'http-equiv="refresh"' in text


class BadgeParser(HTMLParser):
    """Collects badge elements while tracking whether we are inside <footer>."""

    def __init__(self) -> None:
        super().__init__()
        self.badge_count = 0
        self.inside_footer_depth = 0
        self.badge_started_in_footer = False
        self.in_badge = 0
        self.anchors: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []

    def handle_starttag(self, tag, attrs) -> None:
        attr = {k.lower(): (v or "") for k, v in attrs}
        if tag == "footer":
            self.inside_footer_depth += 1
        if tag == "div" and attr.get("data-badge") == "aiagentsdirectory":
            self.badge_count += 1
            self.badge_started_in_footer = self.inside_footer_depth > 0
            self.in_badge += 1
        elif self.in_badge > 0:
            if tag == "a":
                self.anchors.append(attr)
            elif tag == "img":
                self.images.append(attr)

    def handle_endtag(self, tag) -> None:
        if tag == "footer" and self.inside_footer_depth > 0:
            self.inside_footer_depth -= 1
        if self.in_badge > 0 and tag == "div":
            self.in_badge -= 1


def parse_anchor_failures(rel: str, anchors: list[dict[str, str]]) -> list[str]:
    failures: list[str] = []
    if len(anchors) != 1:
        failures.append(f"{rel}: badge must contain exactly one <a>, found {len(anchors)}")
        return failures
    a = anchors[0]
    href = html.unescape(a.get("href", ""))
    if not href.startswith(WANTED_HREF_PREFIX):
        failures.append(f"{rel}: badge href wrong: {href!r} (want prefix {WANTED_HREF_PREFIX})")
    if a.get("target") != "_blank":
        failures.append(f"{rel}: badge <a> target={a.get('target')!r}, want \"_blank\"")
    rel_values = a.get("rel", "").split()
    if "noopener" not in rel_values:
        failures.append(f"{rel}: badge <a> rel must contain noopener, got {a.get('rel')!r}")
    return failures


def parse_image_failures(rel: str, images: list[dict[str, str]]) -> list[str]:
    failures: list[str] = []
    if len(images) != 1:
        failures.append(f"{rel}: badge must contain exactly one <img>, found {len(images)}")
        return failures
    img = images[0]
    src = html.unescape(img.get("src", ""))
    if src != WANTED_IMG_SRC:
        failures.append(f"{rel}: badge img src wrong: {src!r}")
    if img.get("width") != WANTED_WIDTH:
        failures.append(f"{rel}: badge img width={img.get('width')!r}, want {WANTED_WIDTH}")
    if img.get("height") != WANTED_HEIGHT:
        failures.append(f"{rel}: badge img height={img.get('height')!r}, want {WANTED_HEIGHT}")
    return failures


def main() -> int:
    files = sorted(p for p in ROOT.rglob("*.html") if not p.is_relative_to(SKIP_DIR))
    failures: list[str] = []
    footer_pages = 0
    badged_pages = 0
    badgeless_footerless_pages = 0

    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(ROOT))

        # (skip) footerless pages (meta-refresh redirect stubs, etc.)
        if is_merge_stub(text) or "<footer" not in text.lower():
            badgeless_footerless_pages += 1
            continue
        footer_pages += 1

        # (1) exactly one badge element
        parser = BadgeParser()
        try:
            parser.feed(text)
        except Exception as e:  # pragma: no cover
            failures.append(f"{rel}: HTML parse error: {e}")
            continue
        if not (0 < parser.badge_count <= 1):
            failures.append(f"{rel}: found {parser.badge_count} data-badge elements, want exactly 1")
        badged_pages += 1 if parser.badge_count == 1 else 0

        # (2) inside the footer
        if parser.badge_count > 0 and not parser.badge_started_in_footer:
            failures.append(f"{rel}: data-badge element is not inside the footer")

        failures.extend(parse_anchor_failures(rel, parser.anchors))
        failures.extend(parse_image_failures(rel, parser.images))

    print(f"Files scanned             : {len(files)}")
    print(f"Pages with <footer>       : {footer_pages}")
    print(f"Pages with 1 valid badge  : {badged_pages}")
    print(f"Footerless pages skipped  : {badgeless_footerless_pages}")
    print(f"Failures                  : {len(failures)}")
    for f in failures[:50]:
        print(f"  {f}")
    if len(failures) > 50:
        print(f"  ... and {len(failures) - 50} more")
    if not failures:
        print("\nOK: AI Agents Directory badge present and correct in every footer.")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
