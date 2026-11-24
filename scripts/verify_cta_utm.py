#!/usr/bin/env python3
"""Verify cta_click link_domain patch + UTM passthrough on app.snugs.ai CTAs (#45).

Checks:
  a) Find all HTML files with data-cta / cta_click.
  b) Assert every cta_click payload includes link_domain.
  c) Assert app.snugs.ai CTA hrefs include utm_source=marketing_site,
     utm_medium=cta, and a non-empty utm_campaign (static defaults).
  d) Assert all HTML pages with app.snugs.ai CTAs include /assets/js/cta-utm.js.
  e) Assert runtime passthrough works for producthunt on 3 CTAs
     (home-pricing-yearly, home-hero, home-footer) preserving plan and placement.
  f) Assert no-inbound default preserves marketing_site.
  g) Assert badge and non-app outbound links are not rewritten.
  h) Print counts (pages patched, CTAs checked, failures).
"""

import html
import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "assets" / "js" / "cta-utm.js"
SKIP_DIR = ROOT / "og" / "brand" / "templates"

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


def run_node_transform(href: str, placement: str, inbound: dict | None) -> str:
    """Evaluate updateCtaUrl via Node.js."""
    node_code = f"""
    const ctaUtm = require({json.dumps(str(SCRIPT_PATH))});
    const res = ctaUtm.updateCtaUrl({json.dumps(href)}, {json.dumps(placement)}, {json.dumps(inbound)});
    console.log(JSON.stringify(res));
    """
    proc = subprocess.run(
        ["node", "-e", node_code],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip())


def verify_producthunt_and_defaults() -> list[str]:
    """Verify runtime passthrough with producthunt and default scenarios."""
    failures: list[str] = []
    if not SCRIPT_PATH.is_file():
        return [f"Script not found: {SCRIPT_PATH.relative_to(ROOT)}"]

    inbound_ph = {"utm_source": "producthunt"}

    # 1. Yearly pricing CTA with ?utm_source=producthunt
    yearly_href = (
        "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&"
        "utm_campaign=home-pricing-yearly&plan=yearly"
    )
    res_yearly = run_node_transform(yearly_href, "home-pricing-yearly", inbound_ph)
    parsed_yearly = urlparse(res_yearly)
    params_yearly = parse_qs(parsed_yearly.query)
    if params_yearly.get("utm_source") != ["producthunt"]:
        failures.append(f"Yearly CTA producthunt utm_source failed: got {params_yearly.get('utm_source')}")
    if params_yearly.get("plan") != ["yearly"]:
        failures.append(f"Yearly CTA plan param missing or altered: got {params_yearly.get('plan')}")
    placement_yearly = params_yearly.get("cta", [""])[0] or params_yearly.get("utm_content", [""])[0]
    if placement_yearly != "home-pricing-yearly":
        failures.append(f"Yearly CTA placement missing in cta/utm_content: got {placement_yearly}")
    if params_yearly.get("utm_campaign") == ["home-pricing-yearly"]:
        failures.append("Yearly CTA campaign was overwritten with placement")

    # 2. Hero CTA with ?utm_source=producthunt
    hero_href = (
        "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&"
        "utm_campaign=home-hero"
    )
    res_hero = run_node_transform(hero_href, "home-hero", inbound_ph)
    parsed_hero = urlparse(res_hero)
    params_hero = parse_qs(parsed_hero.query)
    if params_hero.get("utm_source") != ["producthunt"]:
        failures.append(f"Hero CTA producthunt utm_source failed: got {params_hero.get('utm_source')}")
    placement_hero = params_hero.get("cta", [""])[0] or params_hero.get("utm_content", [""])[0]
    if placement_hero != "home-hero":
        failures.append(f"Hero CTA placement missing: got {placement_hero}")

    # 3. Footer CTA with ?utm_source=producthunt
    footer_href = (
        "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&"
        "utm_campaign=home-footer"
    )
    res_footer = run_node_transform(footer_href, "home-footer", inbound_ph)
    parsed_footer = urlparse(res_footer)
    params_footer = parse_qs(parsed_footer.query)
    if params_footer.get("utm_source") != ["producthunt"]:
        failures.append(f"Footer CTA producthunt utm_source failed: got {params_footer.get('utm_source')}")
    placement_footer = params_footer.get("cta", [""])[0] or params_footer.get("utm_content", [""])[0]
    if placement_footer != "home-footer":
        failures.append(f"Footer CTA placement missing: got {placement_footer}")

    # 4. No-inbound default
    res_default = run_node_transform(yearly_href, "home-pricing-yearly", None)
    parsed_default = urlparse(res_default)
    params_default = parse_qs(parsed_default.query)
    if params_default.get("utm_source") != ["marketing_site"]:
        failures.append(f"Default utm_source failed: got {params_default.get('utm_source')}")
    if params_default.get("utm_campaign") != ["home-pricing-yearly"]:
        failures.append(f"Default utm_campaign failed: got {params_default.get('utm_campaign')}")
    if params_default.get("plan") != ["yearly"]:
        failures.append(f"Default plan param failed: got {params_default.get('plan')}")

    # 5. Non-app links / badge links
    badge_href = (
        "https://aiagentsdirectory.com/agent/snugsai?utm_source=badge&utm_medium=referral&"
        "utm_campaign=free_listing&utm_content=snugsai"
    )
    res_badge = run_node_transform(badge_href, "badge", inbound_ph)
    if res_badge != badge_href:
        failures.append(f"Badge link was rewritten: got {res_badge}")

    return failures


def verify() -> int:
    html_files = sorted(
        p for p in ROOT.rglob("*.html") if ".git" not in p.parts
    )

    pages_with_cta = 0
    pages_missing_link_domain: list[str] = []
    pages_missing_script: list[str] = []
    cta_total = 0
    cta_app = 0
    utm_failures: list[str] = []

    for path in html_files:
        if path.is_relative_to(SKIP_DIR):
            continue
        text = path.read_text(encoding="utf-8")

        has_cta = "cta_click" in text or "data-cta" in text
        if not has_cta:
            continue
        pages_with_cta += 1

        # Check script inclusion
        if "app.snugs.ai" in text and "assets/js/cta-utm.js" not in text:
            pages_missing_script.append(str(path.relative_to(ROOT)))

        # (b) every cta_click payload must include link_domain
        if "cta_click" in text and "link_domain" not in text:
            pages_missing_link_domain.append(str(path.relative_to(ROOT)))

        # (c) check static default UTM passthrough on app.snugs.ai CTA hrefs
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

    runtime_failures = verify_producthunt_and_defaults()

    failures = (
        len(pages_missing_link_domain)
        + len(pages_missing_script)
        + len(utm_failures)
        + len(runtime_failures)
    )

    print(f"Pages with data-cta / cta_click : {pages_with_cta}")
    print(f"Pages missing link_domain        : {len(pages_missing_link_domain)}")
    print(f"Pages missing cta-utm.js script  : {len(pages_missing_script)}")
    print(f"CTAs checked (all hrefs)         : {cta_total}")
    print(f"CTAs pointing at app.snugs.ai    : {cta_app}")
    print(f"Static UTM failures              : {len(utm_failures)}")
    print(f"Runtime passthrough failures     : {len(runtime_failures)}")

    if pages_missing_link_domain:
        print("\n--- pages missing link_domain ---")
        for p in pages_missing_link_domain:
            print(f"  {p}")
    if pages_missing_script:
        print("\n--- pages missing cta-utm.js script ---")
        for p in pages_missing_script:
            print(f"  {p}")
    if utm_failures:
        print("\n--- UTM failures ---")
        for f in utm_failures:
            print(f"  {f}")
    if runtime_failures:
        print("\n--- Runtime passthrough failures ---")
        for r in runtime_failures:
            print(f"  {r}")

    if failures == 0:
        print("\nOK: all cta_click payloads include link_domain, all "
              "app.snugs.ai CTAs include cta-utm.js, and producthunt "
              "passthrough rules are verified.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(verify())
