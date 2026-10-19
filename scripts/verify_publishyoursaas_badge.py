#!/usr/bin/env python3
"""Verify the PublishYourSaaS "Listed on" badge in every page footer.

Checks (issue #135):
  1) Every .html file with a <footer> element contains exactly ONE
     data-badge="publishyoursaas" element (og/brand/templates/* email
     templates are exempt).
  2) The badge is located INSIDE the footer element (between <footer ...>
     and its closing </footer>).
  3) The badge <a> href is exactly https://publishyoursaas.com (trailing
     slash allowed), opens in a new tab (target="_blank") and rel contains
     "noopener".
  4) The badge <img> src is https://publishyoursaas.com/publishyoursaas-badge.svg
     with width=200 and height=50.
  5) The badge is in the same data-badge-row="footer" container as the
     aiagentsdirectory badge (both badges are sibling divs inside the row).
  6) The row container has class "mt-6 flex flex-wrap justify-center items-center gap-3 sm:gap-4".
  7) Each badge div has class "flex justify-center w-40 sm:w-auto".
Footerless meta-refresh redirect stubs in resources/ and pages without a
footer are not part of the badge surface, so they are not checked.
"""

import html
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIR = ROOT / "og" / "brand" / "templates"

BADGE_MARK = 'data-badge="publishyoursaas"'
WANTED_HREF = "https://publishyoursaas.com"
WANTED_IMG_SRC = "https://publishyoursaas.com/publishyoursaas-badge.svg"
WANTED_WIDTH = "200"
WANTED_HEIGHT = "50"
ROW_CLASS = 'mt-6 flex flex-wrap justify-center items-center gap-3 sm:gap-4'
BADGE_DIV_CLASS = 'flex justify-center w-40 sm:w-auto'


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
        if tag == "div" and attr.get("data-badge") == "publishyoursaas":
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
    # Allow trailing slash
    if href not in (WANTED_HREF, WANTED_HREF + "/"):
        failures.append(f"{rel}: badge href wrong: {href!r} (want {WANTED_HREF} or {WANTED_HREF}/)")
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


def check_row_container(text: str, rel: str) -> list[str]:
    """Check that both badges are inside a shared data-badge-row="footer" container with correct classes."""
    failures: list[str] = []
    # Find the row container
    row_start = text.find('data-badge-row="footer"')
    if row_start == -1:
        failures.append(f"{rel}: no data-badge-row=\"footer\" container found")
        return failures
    # Find the opening <div of the row container
    div_start = text.rfind("<div", 0, row_start)
    if div_start == -1:
        failures.append(f"{rel}: row container div start not found")
        return failures
    # Find the class attribute in the row div
    class_pos = text.find('class="', div_start, row_start)
    if class_pos == -1:
        failures.append(f"{rel}: row container class attribute not found")
        return failures
    class_end = text.find('"', class_pos + 7)
    if class_end == -1:
        failures.append(f"{rel}: row container class attribute not closed")
        return failures
    row_class = text[class_pos + 7:class_end]
    if row_class != ROW_CLASS:
        failures.append(f"{rel}: row container class mismatch: got {row_class!r}, want {ROW_CLASS!r}")
    # Find the matching closing </div>
    depth = 0
    i = div_start
    row_end = -1
    while i < len(text):
        if text[i:i+4] == "<div":
            depth += 1
            i += 4
        elif text[i:i+5] == "</div":
            depth -= 1
            if depth == 0:
                row_end = i + 5
                break
            i += 5
        else:
            i += 1
    if row_end == -1:
        failures.append(f"{rel}: row container closing </div> not found")
        return failures
    row_html = text[div_start:row_end]
    # Check both badges are inside
    if 'data-badge="aiagentsdirectory"' not in row_html:
        failures.append(f"{rel}: row container missing aiagentsdirectory badge")
    if 'data-badge="publishyoursaas"' not in row_html:
        failures.append(f"{rel}: row container missing publishyoursaas badge")

    # Check badge div classes
    for badge_name in ("aiagentsdirectory", "publishyoursaas"):
        badge_pos = row_html.find(f'data-badge="{badge_name}"')
        if badge_pos == -1:
            continue
        badge_div_start = row_html.rfind("<div", 0, badge_pos)
        if badge_div_start == -1:
            failures.append(f"{rel}: {badge_name} badge div start not found")
            continue
        badge_class_pos = row_html.find('class="', badge_div_start, badge_pos)
        if badge_class_pos == -1:
            failures.append(f"{rel}: {badge_name} badge div class attribute not found")
            continue
        badge_class_end = row_html.find('"', badge_class_pos + 7)
        if badge_class_end == -1:
            failures.append(f"{rel}: {badge_name} badge div class attribute not closed")
            continue
        badge_div_class = row_html[badge_class_pos + 7:badge_class_end]
        if badge_div_class != BADGE_DIV_CLASS:
            failures.append(f"{rel}: {badge_name} badge div class mismatch: got {badge_div_class!r}, want {BADGE_DIV_CLASS!r}")

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
            failures.append(f"{rel}: found {parser.badge_count} data-badge=\"publishyoursaas\" elements, want exactly 1")
        badged_pages += 1 if parser.badge_count == 1 else 0

        # (2) inside the footer
        if parser.badge_count > 0 and not parser.badge_started_in_footer:
            failures.append(f"{rel}: data-badge=\"publishyoursaas\" element is not inside the footer")

        # (3) anchor checks
        failures.extend(parse_anchor_failures(rel, parser.anchors))

        # (4) image checks
        failures.extend(parse_image_failures(rel, parser.images))

        # (5) same row container as aiagentsdirectory badge (with class checks)
        if parser.badge_count > 0:
            failures.extend(check_row_container(text, rel))

        # (6) no stray ">" lines in footer
        footer_start = text.find("<footer")
        if footer_start != -1:
            footer_end = text.find("</footer>", footer_start)
            if footer_end != -1:
                footer_html = text[footer_start:footer_end + len("</footer>")]
                for i, line in enumerate(footer_html.splitlines(), 1):
                    if line.strip() == ">":
                        failures.append(f"{rel}: stray '>' line in footer at relative line {i}")

    print(f"Files scanned                    : {len(files)}")
    print(f"Pages with <footer>              : {footer_pages}")
    print(f"Pages with 1 valid badge         : {badged_pages}")
    print(f"Footerless pages skipped         : {badgeless_footerless_pages}")
    print(f"Failures                         : {len(failures)}")
    for f in failures[:50]:
        print(f"  {f}")
    if len(failures) > 50:
        print(f"  ... and {len(failures) - 50} more")
    if not failures:
        print("\nOK: PublishYourSaaS badge present and correct in every footer.")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())