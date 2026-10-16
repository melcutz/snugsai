#!/usr/bin/env python3
"""Add the AI Agents Directory "Featured on" badge to every page footer.

Targets every .html file that has a <footer> element, repo-wide (issue #14).
Skipped:
  - og/brand/templates/* (transactional email templates)
  - resources/* meta-refresh redirect stub pages (footerless, so never match)
Idempotent: files already containing data-badge="aiagentsdirectory" are skipped.

For each page:
  - The badge block is inserted immediately BEFORE the LAST closing </footer>,
    indented to match that line, so it renders as the last item inside the
    footer element (content is centered via flex justify-center; mt-6 keeps
    spacing consistent with the list above it in every footer variant).
  - The <a> opens the directory profile in a new tab (target="_blank",
    rel="noopener noreferrer") and carries UTM parameters
    (utm_source=badge, utm_medium=referral, utm_campaign=free_listing)
    so AI Agents Directory can attribute the backlink.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIR = ROOT / "og" / "brand" / "templates"

BADGE_MARK = 'data-badge="aiagentsdirectory"'
FOOTER_CLOSE = "</footer>"

BADGE_BLOCK_TEMPLATE = """\
{w}<div class="mt-6 flex justify-center" data-badge="aiagentsdirectory">
{w}  <a href="https://aiagentsdirectory.com/agent/snugsai?utm_source=badge&amp;utm_medium=referral&amp;utm_campaign=free_listing&amp;utm_content=snugsai" target="_blank" rel="noopener noreferrer">
{w}    <img src="https://aiagentsdirectory.com/featured-badge.svg?v=2024" alt="Snugs.ai - Featured on AI Agents Directory" width="200" height="50" class="h-auto max-w-full" loading="lazy" decoding="async" />
{w}  </a>
{w}</div>
"""


def iter_target_files() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*.html") if not p.is_relative_to(SKIP_DIR))


def patch_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if BADGE_MARK in text:
        return "skipped"
    idx = text.rfind(FOOTER_CLOSE)
    if idx == -1:
        return "no-footer"

    # </footer> sits on its own line: match its leading whitespace so the
    # badge block lines up with the footer's closing tag (inner snippet
    # lines keep their relative nesting).
    line_start = text.rfind("\n", 0, idx) + 1
    leading = text[line_start:idx]
    if not (leading.startswith((" ", "\t")) and leading.strip() == ""):
        leading = ""

    text = text[:line_start] + BADGE_BLOCK_TEMPLATE.format(w=leading) + text[line_start:]
    path.write_text(text, encoding="utf-8")
    return "patched"


def main() -> int:
    files = iter_target_files()
    patched = skipped = no_footer = no_match = 0
    for path in files:
        r = patch_file(path)
        if r == "patched":
            patched += 1
        elif r == "skipped":
            skipped += 1
        elif r == "no-footer":
            no_footer += 1
        else:
            no_match += 1
            print(f"  no-match: {path.relative_to(ROOT)}", file=sys.stderr)
    print(f"Files scanned        : {len(files)}")
    print(f"  patched            : {patched}")
    print(f"  skipped (already)  : {skipped}")
    print(f"  no footer          : {no_footer}")
    print(f"  no-match           : {no_match}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
