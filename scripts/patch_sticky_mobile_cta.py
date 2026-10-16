#!/usr/bin/env python3
"""Add dismissible mobile-only sticky "Ask Snugs" trial CTA to article pages.

Targets resources/*.html article pages only (excludes resources/index.html).
Idempotent: files already containing data-cta="sticky_mobile" are skipped.

For each article:
  - CSS goes into the head <style> block (available before first paint,
    so no flash on desktop and no CLS). Base display:none, shown only
    under @media (max-width:767px), hidden on desktop via min-width:768px.
    body padding-bottom reserves space so the fixed bar never covers
    content. z-index 40 keeps future cookie-consent banners (50+) on top.
  - Sticky bar HTML is inserted BEFORE the existing data-cta binder script,
    so the shared querySelectorAll('[data-cta]') handler picks it up with
    zero extra analytics code. The shared handler already sends cta_id,
    link_url and link_domain to GA via gtag cta_click.
  - Sticky href reuses the article's main CTA utm_campaign (fallback:
    filename stem), with utm_source=marketing_site, utm_medium=cta.
"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
RESOURCES = ROOT / "resources"

STICKY_CSS = """    /* Snugs sticky mobile CTA (#10): mobile-only, fixed, no CLS. Keep z-index 40 so cookie consent (50+) stays on top. */
    .snugs-sticky-cta { display: none; }
    @media (max-width: 767px) {
      body { padding-bottom: calc(76px + env(safe-area-inset-bottom, 0px)); }
      body.snugs-sticky-dismissed { padding-bottom: 0; }
      .snugs-sticky-cta {
        display: flex;
        position: fixed;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 40;
        align-items: center;
        gap: 10px;
        padding: 10px 12px calc(10px + env(safe-area-inset-bottom, 0px));
        background: rgba(255, 255, 255, 0.96);
        border-top: 1px solid #fed7aa;
        box-shadow: 0 -8px 24px rgba(234, 88, 12, 0.12);
      }
      .snugs-sticky-cta[hidden] { display: none; }
    }
    @media (min-width: 768px) {
      .snugs-sticky-cta { display: none !important; }
    }
"""

STICKY_HTML_TEMPLATE = """    <!-- Snugs sticky mobile CTA (#10): mobile-only via CSS, dismissible, reuses data-cta/cta_click (cta_id=sticky_mobile). Cookie consent should use z-index 50+. -->
    <div class="snugs-sticky-cta" id="snugs-sticky-cta" role="region" aria-label="Ask Snugs trial">
      <a href="https://app.snugs.ai/?utm_source=marketing_site&amp;utm_medium=cta&amp;utm_campaign={campaign}" data-cta="sticky_mobile" class="flex-1 inline-flex items-center justify-center px-5 py-3 bg-gradient-to-r from-orange-500 to-orange-600 text-white font-bold rounded-full hover:from-orange-600 hover:to-orange-700 transition-all shadow-lg text-sm">Ask Snugs &mdash; Start free trial</a>
      <button type="button" class="snugs-sticky-dismiss flex-shrink-0 w-9 h-9 rounded-full border border-orange-200 bg-white text-gray-600 font-bold leading-none" aria-label="Dismiss trial banner">&times;</button>
    </div>
    <script>
      (function() {{
        var bar = document.getElementById('snugs-sticky-cta');
        if (!bar) return;
        try {{
          if (sessionStorage.getItem('snugs_sticky_dismissed') === '1') {{
            bar.setAttribute('hidden', '');
            document.body.classList.add('snugs-sticky-dismissed');
            return;
          }}
        }} catch (e) {{}}
        var btn = bar.querySelector('.snugs-sticky-dismiss');
        if (btn) {{
          btn.addEventListener('click', function() {{
            bar.setAttribute('hidden', '');
            document.body.classList.add('snugs-sticky-dismissed');
            try {{ sessionStorage.setItem('snugs_sticky_dismissed', '1'); }} catch (e) {{}}
          }});
        }}
      }})();
    </script>
"""

CAMPAIGN_RE = re.compile(r"utm_campaign=([^\"&'\s]+)")


def get_campaign(text: str, fallback: str) -> str:
    m = CAMPAIGN_RE.search(text)
    if m:
        return unquote(m.group(1))
    return fallback


def patch_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if 'data-cta="sticky_mobile"' in text:
        return "skipped"
    if "querySelectorAll('[data-cta]')" not in text and 'querySelectorAll("[data-cta]")' not in text:
        return "no-match"

    campaign = get_campaign(text, path.stem)

    # 1) CSS into head <style>
    if "snugs-sticky-cta" not in text:
        style_close = text.find("</style>")
        if style_close == -1:
            return "no-match"
        text = text[:style_close] + STICKY_CSS + text[style_close:]

    # 2) HTML before the data-cta binder <script>
    binder_idx = text.find("querySelectorAll('[data-cta]')")
    if binder_idx == -1:
        binder_idx = text.find('querySelectorAll("[data-cta]")')
    script_open = text.rfind("<script", 0, binder_idx)
    if script_open == -1:
        return "no-match"
    sticky_html = STICKY_HTML_TEMPLATE.format(campaign=campaign)
    text = text[:script_open] + sticky_html + text[script_open:]

    path.write_text(text, encoding="utf-8")
    return "patched"


def main() -> int:
    files = sorted(p for p in RESOURCES.glob("*.html") if p.name != "index.html")
    patched = skipped = no_match = 0
    for path in files:
        r = patch_file(path)
        if r == "patched":
            patched += 1
        elif r == "skipped":
            skipped += 1
        else:
            no_match += 1
            print(f"  no-match: {path.relative_to(ROOT)}", file=sys.stderr)
    print(f"Article files scanned : {len(files)}")
    print(f"  patched             : {patched}")
    print(f"  skipped (already)   : {skipped}")
    print(f"  no-match            : {no_match}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
