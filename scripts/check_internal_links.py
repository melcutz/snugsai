#!/usr/bin/env python3
"""Check sitemap URLs and in-repo internal links for 404s and broken paths.

Crawl all sitemap URLs, verify source files exist on disk, and ensure
all internal hrefs resolve to existing files or directories.
"""

import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITEMAP = ROOT / "sitemap.xml"
SITE = "https://snugs.ai"


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in ("a", "link"):
            for k, v in attrs:
                if k.lower() == "href" and v:
                    self.hrefs.append(v)


def resolve_internal_target(href: str, source_file: Path) -> tuple[bool, str | None]:
    parsed = urlparse(href)
    if parsed.scheme and parsed.scheme not in ("http", "https"):
        return True, None
    if parsed.netloc and parsed.netloc != "snugs.ai":
        return True, None

    clean_path = parsed.path
    if not clean_path or clean_path == "/":
        return True, None

    if clean_path.startswith("/"):
        target = ROOT / clean_path.lstrip("/")
    else:
        target = source_file.parent / clean_path

    if target.is_dir():
        if (target / "index.html").exists():
            return True, None
        return False, f"Directory missing index.html: {target.relative_to(ROOT)}"
    elif target.exists():
        return True, None
    elif target.with_suffix(".html").exists():
        return True, None
    else:
        return False, f"Missing file: {target.relative_to(ROOT)}"


def main() -> int:
    if not SITEMAP.exists():
        print(f"ERROR: {SITEMAP} not found", file=sys.stderr)
        return 1

    tree = ET.parse(SITEMAP)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text.strip() for e in tree.getroot().findall("s:url/s:loc", ns) if e.text]

    print(f"Crawling {len(locs)} sitemap URLs...")

    broken: list[tuple[str, str, str]] = []

    for loc in locs:
        rel = loc[len(SITE) + 1:] or "index.html"
        if rel.endswith("/"):
            source = ROOT / rel / "index.html"
        else:
            source = ROOT / rel

        if not source.exists():
            broken.append((loc, loc, "Sitemap source file missing on disk"))
            continue

        parser = LinkExtractor()
        try:
            parser.feed(source.read_text(encoding="utf-8", errors="ignore"))
        except Exception as exc:
            broken.append((str(source.relative_to(ROOT)), loc, f"Parse error: {exc}"))
            continue

        for href in parser.hrefs:
            ok, reason = resolve_internal_target(href, source)
            if not ok:
                broken.append((str(source.relative_to(ROOT)), href, reason or "404"))

    # Also check all HTML files in repo for wake-window-calculator.html specifically
    html_files = [p for p in ROOT.rglob("*.html") if ".git" not in p.parts]
    wake_window_broken: list[str] = []
    for hf in html_files:
        content = hf.read_text(encoding="utf-8", errors="ignore")
        if "wake-window-calculator.html" in content:
            wake_window_broken.append(str(hf.relative_to(ROOT)))

    if wake_window_broken:
        print("FAIL: wake-window-calculator.html found in:")
        for w in wake_window_broken:
            print(f"  {w}")

    if broken:
        print(f"FAIL: {len(broken)} broken internal links found:")
        for src, href, reason in broken:
            print(f"  {src} -> {href} ({reason})")

    if not broken and not wake_window_broken:
        print(f"OK: All {len(locs)} sitemap pages crawled with 0 broken internal links.")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
