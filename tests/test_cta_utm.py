#!/usr/bin/env python3
"""Tests for CTA UTM passthrough and first-touch attribution (#45)."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "assets" / "js" / "cta-utm.js"


def run_node_eval(expr: str) -> str:
    """Helper to evaluate JS code using the cta-utm module."""
    node_code = f"""
    const ctaUtm = require({json.dumps(str(SCRIPT_PATH))});
    const result = ({expr});
    console.log(JSON.stringify(result));
    """
    res = subprocess.run(
        ["node", "-e", node_code],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(res.stdout.strip())


def test_cta_utm_script_exists():
    assert SCRIPT_PATH.is_file(), "assets/js/cta-utm.js must exist"
    assert SCRIPT_PATH.stat().st_size > 0, "assets/js/cta-utm.js must not be empty"


def test_html_pages_include_cta_utm_script():
    """Every HTML page with app.snugs.ai CTAs must include cta-utm.js."""
    missing = []
    skip_dir = ROOT / "og" / "brand" / "templates"
    for p in ROOT.rglob("*.html"):
        if ".git" in p.parts or p.is_relative_to(skip_dir):
            continue
        text = p.read_text(encoding="utf-8")
        if "app.snugs.ai" in text and "assets/js/cta-utm.js" not in text:
            missing.append(str(p.relative_to(ROOT)))
    assert not missing, f"HTML pages missing assets/js/cta-utm.js: {missing}"


def test_producthunt_inbound_on_three_ctas():
    """Verify ?utm_source=producthunt test on 3 CTAs: Yearly, hero, footer."""
    inbound = {"utm_source": "producthunt"}

    # 1. Yearly pricing CTA
    yearly_href = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-pricing-yearly&plan=yearly"
    yearly_res = run_node_eval(
        f"ctaUtm.updateCtaUrl({json.dumps(yearly_href)}, 'home-pricing-yearly', {json.dumps(inbound)})"
    )
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(yearly_res)
    params = parse_qs(parsed.query)
    assert parsed.hostname == "app.snugs.ai"
    assert params.get("utm_source") == ["producthunt"]
    assert params.get("utm_medium") == ["cta"]
    assert params.get("plan") == ["yearly"], "plan param must be kept"
    placement = params.get("cta", [""])[0] or params.get("utm_content", [""])[0]
    assert placement == "home-pricing-yearly", "placement must be recorded in cta or utm_content"
    assert params.get("utm_campaign") != ["home-pricing-yearly"]

    # 2. Hero CTA
    hero_href = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-hero"
    hero_res = run_node_eval(
        f"ctaUtm.updateCtaUrl({json.dumps(hero_href)}, 'home-hero', {json.dumps(inbound)})"
    )
    parsed_hero = urlparse(hero_res)
    params_hero = parse_qs(parsed_hero.query)
    assert parsed_hero.hostname == "app.snugs.ai"
    assert params_hero.get("utm_source") == ["producthunt"]
    assert (params_hero.get("cta", [""])[0] or params_hero.get("utm_content", [""])[0]) == "home-hero"

    # 3. Footer CTA
    footer_href = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-footer"
    footer_res = run_node_eval(
        f"ctaUtm.updateCtaUrl({json.dumps(footer_href)}, 'home-footer', {json.dumps(inbound)})"
    )
    parsed_footer = urlparse(footer_res)
    params_footer = parse_qs(parsed_footer.query)
    assert parsed_footer.hostname == "app.snugs.ai"
    assert params_footer.get("utm_source") == ["producthunt"]
    assert (params_footer.get("cta", [""])[0] or params_footer.get("utm_content", [""])[0]) == "home-footer"


def test_no_inbound_default_preserves_marketing_site():
    yearly_href = "https://app.snugs.ai/?utm_source=marketing_site&utm_medium=cta&utm_campaign=home-pricing-yearly&plan=yearly"
    res = run_node_eval(
        f"ctaUtm.updateCtaUrl({json.dumps(yearly_href)}, 'home-pricing-yearly', null)"
    )
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(res)
    params = parse_qs(parsed.query)
    assert params.get("utm_source") == ["marketing_site"]
    assert params.get("utm_medium") == ["cta"]
    assert params.get("utm_campaign") == ["home-pricing-yearly"]
    assert params.get("plan") == ["yearly"]


def test_badge_and_outbound_links_untouched():
    inbound = {"utm_source": "producthunt"}
    badge_href = "https://aiagentsdirectory.com/agent/snugsai?utm_source=badge&utm_medium=referral&utm_campaign=free_listing&utm_content=snugsai"
    res = run_node_eval(
        f"ctaUtm.updateCtaUrl({json.dumps(badge_href)}, 'badge', {json.dumps(inbound)})"
    )
    assert res == badge_href
