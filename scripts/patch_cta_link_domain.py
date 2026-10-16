#!/usr/bin/env python3
"""Patch every inline cta_click gtag handler to include link_domain.

The handler is duplicated inline across ~474 HTML pages (index.html,
resources/*.html, tools/*.html, etc.). This script rewrites the payload so a
test click reports link_domain in GA4 DebugView, e.g.:

    gtag('event', 'cta_click', {
        cta_id: el.getAttribute('data-cta'),
        link_url: el.href,
        link_domain: (function(){ try { return new URL(el.href).hostname; } catch(e){ return 'unknown'; } })()
    });

The per-page inline pattern is preserved (no shared external JS file), so the
site keeps working offline / over file://. The script is idempotent: pages
that already contain link_domain are skipped.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Matches the `link_url: el.href` line inside a cta_click payload, capturing
# the leading indentation so the new link_domain line lines up with it.
LINK_URL_RE = re.compile(r"\n(\s+)(link_url: el\.href)\n")

LINK_DOMAIN_LINE = (
    "link_domain: (function(){ try { return new URL(el.href).hostname; } "
    "catch(e){ return 'unknown'; } })()"
)


def patch_file(path: Path) -> str:
    """Return 'patched', 'skipped', or 'no-match' for a single HTML file."""
    text = path.read_text(encoding="utf-8")

    if "link_domain" in text:
        return "skipped"
    if "link_url: el.href" not in text:
        return "no-match"

    def repl(match: re.Match) -> str:
        indent, content = match.group(1), match.group(2)
        return f"\n{indent}{content},\n{indent}{LINK_DOMAIN_LINE}\n"

    new_text, count = LINK_URL_RE.subn(repl, text)
    if count == 0:
        return "no-match"

    path.write_text(new_text, encoding="utf-8")
    return "patched"


def main() -> int:
    html_files = sorted(ROOT.rglob("*.html"))
    patched = skipped = no_match = 0

    for path in html_files:
        # Skip anything under .git just in case.
        if ".git" in path.parts:
            continue
        result = patch_file(path)
        if result == "patched":
            patched += 1
        elif result == "skipped":
            skipped += 1
        else:
            no_match += 1

    print(f"HTML files scanned : {len(html_files)}")
    print(f"  patched          : {patched}")
    print(f"  skipped (already): {skipped}")
    print(f"  no cta_click     : {no_match}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
