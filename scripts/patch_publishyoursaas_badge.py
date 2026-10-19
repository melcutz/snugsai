#!/usr/bin/env python3
"""Add the PublishYourSaaS "Listed on" badge to every page footer, next to the
AI Agents Directory badge.

Targets every .html file that has a <footer> element, repo-wide (issue #135).
Skipped:
  - og/brand/templates/* (transactional email templates)
  - resources/* meta-refresh redirect stub pages (footerless, so never match)
Idempotent: files already containing data-badge="publishyoursaas" are skipped,
and already-patched rows are upgraded to the latest class values.

For each page:
  - The existing AI Agents Directory badge div (data-badge="aiagentsdirectory")
    is wrapped together with the new PublishYourSaaS badge div inside a single
    row container (data-badge-row="footer") so they sit side by side on desktop
    and wrap/stack centered on mobile.
  - The mt-6 spacing moves from the aiagentsdirectory div to the row container.
  - The new badge uses the exact href https://publishyoursaas.com (no UTM/query
    string; the directory verifies the backlink).
  - The badge image is exactly 200x50 (the SVG is 240x60, so this matches the
    existing 200x50 badge).
  - The existing aiagentsdirectory badge's inner <a>/<img> markup is preserved
    byte-for-byte (only re-indented), including "&".
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIR = ROOT / "og" / "brand" / "templates"

EXISTING_BADGE_MARK = 'data-badge="aiagentsdirectory"'
NEW_BADGE_MARK = 'data-badge="publishyoursaas"'
ROW_MARK = 'data-badge-row="footer"'
FOOTER_CLOSE = "</footer>"

# Current target classes (v2: gap-3 sm:gap-4 on row, w-40 sm:w-auto on badge divs)
ROW_CLASS = 'mt-6 flex flex-wrap justify-center items-center gap-3 sm:gap-4'
BADGE_DIV_CLASS = 'flex justify-center w-40 sm:w-auto'

# Row container wrapping both badges (Tailwind only; all target pages have Tailwind)
ROW_CONTAINER_TEMPLATE = f"""\
{{w}}<div class="{ROW_CLASS}" data-badge-row="footer">
{{w}}  <div class="{BADGE_DIV_CLASS}" data-badge="aiagentsdirectory">
{{existing_inner}}
{{w}}  </div>
{{w}}  <div class="{BADGE_DIV_CLASS}" data-badge="publishyoursaas">
{{w}}    <a href="https://publishyoursaas.com" target="_blank" rel="noopener noreferrer">
{{w}}      <img src="https://publishyoursaas.com/publishyoursaas-badge.svg" alt="Snugs.ai - Listed on PublishYourSaaS" width="200" height="50" class="h-auto max-w-full" loading="lazy" decoding="async" />
{{w}}    </a>
{{w}}  </div>
{{w}}</div>"""


def iter_target_files() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*.html") if not p.is_relative_to(SKIP_DIR))


def patch_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")

    # Check if the row container already exists
    row_start = text.find(ROW_MARK)
    if row_start != -1:
        # Row exists - check if classes need upgrading
        # Find the opening <div of the row container
        div_start = text.rfind("<div", 0, row_start)
        if div_start == -1:
            return "no-row-div-start"

        # Find the class attribute in the row div
        class_pos = text.find('class="', div_start, row_start)
        if class_pos == -1:
            return "no-row-class"

        class_end = text.find('"', class_pos + 7)
        if class_end == -1:
            return "no-row-class-end"

        current_row_class = text[class_pos + 7:class_end]
        if current_row_class == ROW_CLASS:
            # Row class is already correct, check badge div classes
            new_text, status = _upgrade_badge_divs_if_needed(text)
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
            return status
        else:
            # Upgrade row class
            new_text = text[:class_pos + 7] + ROW_CLASS + text[class_end:]
            # Also upgrade badge divs
            new_text, status = _upgrade_badge_divs_if_needed(new_text)
            path.write_text(new_text, encoding="utf-8")
            return status

    # No row container - check if publishyoursaas badge already exists (shouldn't happen without row, but safety)
    if NEW_BADGE_MARK in text:
        return "skipped"

    # Find the existing aiagentsdirectory badge div
    badge_start = text.find(EXISTING_BADGE_MARK)
    if badge_start == -1:
        return "no-existing-badge"

    # Find the opening <div> of that badge (search backwards for <div)
    div_start = text.rfind("<div", 0, badge_start)
    if div_start == -1:
        return "no-div-start"

    # Find the closing </div> of that badge (search forward) including the '>'
    depth = 0
    i = div_start
    badge_div_end = -1
    while i < len(text):
        if text[i:i+4] == "<div":
            depth += 1
            i += 4
        elif text[i:i+5] == "</div":
            depth -= 1
            if depth == 0:
                # Find the closing '>' of this </div>
                j = i + 5
                while j < len(text) and text[j] != '>':
                    j += 1
                if j < len(text):
                    badge_div_end = j + 1  # include the '>'
                else:
                    badge_div_end = i + 5  # fallback, shouldn't happen
                break
            i += 5
        else:
            i += 1

    if badge_div_end == -1:
        return "no-div-end"

    # Get the leading whitespace of the badge div line (L)
    line_start = text.rfind("\n", 0, div_start) + 1
    leading = text[line_start:div_start]
    if not (leading.startswith((" ", "\t")) and leading.strip() == ""):
        leading = ""

    # Extract the existing badge's inner content (the <a>...</a>) preserving byte-for-byte
    # Find the '>' after the opening <div ... data-badge="aiagentsdirectory">
    inner_start = text.find(">", badge_start) + 1
    if inner_start == 0:  # not found
        return "no-inner-start"
    # The inner content ends before the closing </div>
    inner_end = text.rfind("</div", div_start, badge_div_end)
    if inner_end == -1:
        return "no-inner-end"
    existing_inner = text[inner_start:inner_end]

    # Process the existing inner content:
    # 1. Split into lines (keep newlines)
    # 2. Remove blank/whitespace-only lines
    # 3. Strip leading whitespace from each line
    # 4. Re-indent: <a> and </a> at L+4, <img> at L+6
    # 5. Preserve newlines
    inner_lines = existing_inner.splitlines(keepends=True)
    reindented_lines = []
    for line in inner_lines:
        stripped = line.strip()
        if stripped == "":
            continue  # skip blank/whitespace-only lines
        if stripped.startswith("<a ") or stripped.startswith("</a>"):
            reindented_lines.append(leading + "    " + stripped + "\n")
        elif stripped.startswith("<img ") or stripped.startswith("<img"):
            reindented_lines.append(leading + "      " + stripped + "\n")
        else:
            # Fallback: indent by 4 spaces
            reindented_lines.append(leading + "    " + stripped + "\n")

    reindented_inner = "".join(reindented_lines).rstrip("\n")

    # Build new row container with the preserved existing badge inner content
    row_html = ROW_CONTAINER_TEMPLATE.format(w=leading, existing_inner=reindented_inner)

    # Replace the existing badge div (from line_start to badge_div_end) with the row container
    new_text = text[:line_start] + row_html + text[badge_div_end:]
    path.write_text(new_text, encoding="utf-8")
    return "patched"


def _upgrade_badge_divs_if_needed(text: str) -> tuple[str, str]:
    """Upgrade the two badge div classes to the current target class.
    Returns (new_text, status).
    """
    # Find both badge divs inside the row
    aiagents_pos = text.find('data-badge="aiagentsdirectory"')
    publish_pos = text.find('data-badge="publishyoursaas"')

    if aiagents_pos == -1 or publish_pos == -1:
        return text, "badge-div-missing"

    new_text = text
    changed = False

    for badge_pos in (aiagents_pos, publish_pos):
        # Find the opening <div of this badge
        div_start = new_text.rfind("<div", 0, badge_pos)
        if div_start == -1:
            return text, "no-badge-div-start"

        # Find the class attribute
        class_pos = new_text.find('class="', div_start, badge_pos)
        if class_pos == -1:
            return text, "no-badge-class"

        class_end = new_text.find('"', class_pos + 7)
        if class_end == -1:
            return text, "no-badge-class-end"

        current_class = new_text[class_pos + 7:class_end]
        if current_class != BADGE_DIV_CLASS:
            new_text = new_text[:class_pos + 7] + BADGE_DIV_CLASS + new_text[class_end:]
            changed = True

    if changed:
        return new_text, "upgraded"
    return new_text, "already-current"


def main() -> int:
    files = iter_target_files()
    patched = skipped = upgraded = already_current = no_existing_badge = no_div_start = no_div_end = no_inner_start = no_inner_end = 0
    row_errors = badge_errors = 0
    for path in files:
        r = patch_file(path)
        if r == "patched":
            patched += 1
        elif r == "skipped":
            skipped += 1
        elif r == "upgraded":
            upgraded += 1
        elif r == "already-current":
            already_current += 1
        elif r == "no-existing-badge":
            no_existing_badge += 1
        elif r == "no-div-start":
            no_div_start += 1
        elif r == "no-div-end":
            no_div_end += 1
        elif r == "no-inner-start":
            no_inner_start += 1
        elif r == "no-inner-end":
            no_inner_end += 1
        elif r in ("no-row-div-start", "no-row-class", "no-row-class-end"):
            row_errors += 1
        elif r in ("badge-div-missing", "no-badge-div-start", "no-badge-class", "no-badge-class-end"):
            badge_errors += 1
        else:
            print(f"  unknown result: {path.relative_to(ROOT)}: {r}", file=sys.stderr)
    print(f"Files scanned        : {len(files)}")
    print(f"  patched (new)      : {patched}")
    print(f"  skipped (no badge) : {skipped}")
    print(f"  upgraded           : {upgraded}")
    print(f"  already current    : {already_current}")
    print(f"  no existing badge  : {no_existing_badge}")
    print(f"  no div start       : {no_div_start}")
    print(f"  no div end         : {no_div_end}")
    print(f"  no inner start     : {no_inner_start}")
    print(f"  no inner end       : {no_inner_end}")
    print(f"  row errors         : {row_errors}")
    print(f"  badge div errors   : {badge_errors}")
    return 0


if __name__ == "__main__":
    sys.exit(main())