#!/usr/bin/env python3
"""Include /assets/js/cta-utm.js in pages where CTAs live (#45).

Idempotent: skips files already containing assets/js/cta-utm.js.
Skips redirect stub pages and transactional email templates.
Inserts the defer script before </head>.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIR = ROOT / "og" / "brand" / "templates"

SCRIPT_TAG = '<script defer src="/assets/js/cta-utm.js"></script>'
MARK = "assets/js/cta-utm.js"
HEAD_CLOSE_RE = re.compile(r"(\n([ \t]*))</head>", re.IGNORECASE)


def iter_target_files() -> list[Path]:
    return sorted(
        p
        for p in ROOT.rglob("*.html")
        if not p.is_relative_to(SKIP_DIR) and ".git" not in p.parts
    )


def patch_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if MARK in text:
        return "skipped"
    if 'http-equiv="refresh"' in text:
        return "redirect-stub"

    m = HEAD_CLOSE_RE.search(text)
    if not m:
        return "no-head"

    newline_and_indent = m.group(1)
    base_indent = m.group(2)
    tag_indent = base_indent + "  "

    replacement = (
        f"{newline_and_indent}{tag_indent}<!-- CTA UTM Passthrough & First-Touch Attribution (#45) -->"
        f"{newline_and_indent}{tag_indent}{SCRIPT_TAG}"
        f"{newline_and_indent}</head>"
    )
    new_text = text[: m.start()] + replacement + text[m.end() :]
    path.write_text(new_text, encoding="utf-8")
    return "patched"


def main() -> int:
    files = iter_target_files()
    counts = {"patched": 0, "skipped": 0, "redirect-stub": 0, "no-head": 0}

    for f in files:
        res = patch_file(f)
        counts[res] = counts.get(res, 0) + 1

    print(f"Scanned {len(files)} files:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
