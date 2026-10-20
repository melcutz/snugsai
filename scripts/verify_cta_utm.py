#!/usr/bin/env python3
"""Verify cta_click link_domain patch + UTM passthrough on app.snugs.ai CTAs.

Checks:
  a) Find all HTML files with data-cta / cta_click.
  b) Assert every cta_click payload includes link_domain.
  c) Assert app.snugs.ai CTA hrefs include utm_source=marketing_site,
     utm_medium=cta, and a non-empty utm_campaign.
  d) Print counts (pages patched, CTAs checked, failures).
"""

import html
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_UTM = {"utm_source": "marketing_site", "utm_medium": "cta"}


class CtaAnchorParser(HTMLParser):
    """Collect hrefs of every <a> that carries a data-cta attribute."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr = {k.lower(): v for k, v in attrs}
        if "data-cta" in attr and attr.get("href"):
            self.hrefs.append(attr["href"])


def verify() -> int:
    html_files = sorted(
        p for p in ROOT.rglob("*.html") if ".git" not in p.parts
    )

    pages_with_cta = 0
    pages_missing_link_domain: list[str] = []
    cta_total = 0
    cta_app = 0
    utm_failures: list[str] = []

    for path in html_files:
        text = path.read_text(encoding="utf-8")

        has_cta = "cta_click" in text or "data-cta" in text
        if not has_cta:
            continue
        pages_with_cta += 1

        # (b) every cta_click payload must include link_domain
        if "cta_click" in text and "link_domain" not in text:
            pages_missing_link_domain.append(str(path.relative_to(ROOT)))

        # (c) check UTM passthrough on app.snugs.ai CTA hrefs
        parser = CtaAnchorParser()
        parser.feed(text)
        for raw_href in parser.hrefs:
            cta_total += 1
            href = html.unescape(raw_href)
            parsed = urlparse(href)
            if parsed.hostname != "app.snugs.ai":
                continue
            cta_app += 1
            params = parse_qs(parsed.query)
            missing = [
                f"{k}={v}"
                for k, v in REQUIRED_UTM.items()
                if params.get(k, [""])[0] != v
            ]
            campaign = params.get("utm_campaign", [""])[0]
            if not campaign:
                missing.append("utm_campaign=<empty>")
            if missing:
                utm_failures.append(
                    f"{path.relative_to(ROOT)}: {href}  ->  missing {', '.join(missing)}"
                )

    failures = len(pages_missing_link_domain) + len(utm_failures)

    print(f"Pages with data-cta / cta_click : {pages_with_cta}")
    print(f"Pages missing link_domain        : {len(pages_missing_link_domain)}")
    print(f"CTAs checked (all hrefs)         : {cta_total}")
    print(f"CTAs pointing at app.snugs.ai    : {cta_app}")
    print(f"UTM failures                      : {len(utm_failures)}")

    if pages_missing_link_domain:
        print("\n--- pages missing link_domain ---")
        for p in pages_missing_link_domain:
            print(f"  {p}")
    if utm_failures:
        print("\n--- UTM failures ---")
        for f in utm_failures:
            print(f"  {f}")

    if failures == 0:
        print("\nOK: all cta_click payloads include link_domain and all "
              "app.snugs.ai CTAs carry the required UTM params.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(verify())
