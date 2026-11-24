"""Tests for article breadcrumbs, JSON-LD schema, and Related Guides (#34)."""

import csv
import html
import json
import re
from pathlib import Path
from xml.etree import ElementTree

BASE = Path(__file__).resolve().parent.parent
RESOURCES = BASE / "resources"


def get_keep_resource_slugs():
    csv_path = BASE / "seo" / "classification.csv"
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    return {
        r["path"].replace("resources/", "").replace(".html", "")
        for r in rows
        if r["decision"] == "keep" and r["path"].startswith("resources/")
    }


def get_all_article_files():
    files = sorted(RESOURCES.glob("*.html"))
    articles = []
    for f in files:
        if f.name == "index.html":
            continue
        text = f.read_text(encoding="utf-8")
        if 'http-equiv="refresh"' in text:
            continue
        articles.append((f, text))
    return articles


def test_qa_example_article():
    """Verify the QA example: mastering-baby-naps-from-contact-naps-to-independent-sleep.html."""
    qa_file = RESOURCES / "mastering-baby-naps-from-contact-naps-to-independent-sleep.html"
    assert qa_file.exists(), "QA example file must exist"
    text = qa_file.read_text(encoding="utf-8")

    title_match = re.search(r"<title>(.*?)</title>", text)
    assert title_match, "Title must be present"
    full_title = title_match.group(1).strip()
    article_title = full_title.replace(" | Snugs.ai", "").strip()
    assert article_title == "Mastering Baby Naps: From Contact Naps to Independent Sleep"

    # Visible breadcrumb nav
    nav_match = re.search(r'<nav class="text-sm text-gray-600 mb-6 animate-fadeIn">(.*?)</nav>', text, re.S)
    assert nav_match, "Visible breadcrumb nav must be present"
    nav_html = nav_match.group(1)

    assert '<a href="/"' in nav_html, "Home link must be /"
    assert '<a href="/resources/"' in nav_html, "Resources link must be /resources/"
    assert "Calm a Crying Baby" not in nav_html, "Leftover Calm a Crying Baby must be gone from breadcrumb"

    last_crumb_match = re.search(r'<span class="text-gray-800">(.*?)</span>', nav_html, re.S)
    assert last_crumb_match, "Last crumb must be inside span.text-gray-800"
    last_crumb_text = html.unescape(last_crumb_match.group(1).strip())
    assert last_crumb_text == article_title, f"Last crumb '{last_crumb_text}' must match article title '{article_title}'"

    # JSON-LD BreadcrumbList
    scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)
    assert len(scripts) >= 1, "Must have JSON-LD script"
    data = json.loads(scripts[0])
    graph = data.get("@graph", [data])
    bc = next((node for node in graph if node.get("@type") == "BreadcrumbList"), None)
    assert bc is not None, "BreadcrumbList node must be in JSON-LD"
    items = bc.get("itemListElement", [])
    assert len(items) == 3, "BreadcrumbList must have 3 items"
    assert items[0]["name"] == "Home" and items[0]["item"] == "https://snugs.ai/"
    assert items[1]["name"] == "Resources" and items[1]["item"] == "https://snugs.ai/resources/"
    assert items[2]["name"] == article_title, f"JSON-LD pos 3 name '{items[2]['name']}' must equal article title"
    assert items[2]["item"] == "https://snugs.ai/resources/mastering-baby-naps-from-contact-naps-to-independent-sleep.html"

    # No leftover HowTo "Calm a Crying Baby" schema
    for s in scripts[1:]:
        s_data = json.loads(s)
        assert s_data.get("@type") != "HowTo" or s_data.get("name") != "Calm a Crying Baby"

    # Related Guides
    rg_match = re.search(
        r'<section class="mt-10 pt-8 border-t-2 border-orange-100">\s*<h2[^>]*>Related Guides</h2>\s*<ul[^>]*>(.*?)</ul>\s*</section>',
        text,
        re.S
    )
    assert rg_match, "Related Guides section must be present"
    rg_links = re.findall(r'href="(/resources/[^"]+\.html)"', rg_match.group(1))

    assert 5 <= len(rg_links) <= 12, f"Related Guides must have 5-12 links, got {len(rg_links)}"
    assert len(rg_links) == len(set(rg_links)), "Related Guides links must be unique"
    assert "/resources/mastering-baby-naps-from-contact-naps-to-independent-sleep.html" not in rg_links, "No self-links"

    keep_slugs = get_keep_resource_slugs()
    for link in rg_links:
        slug = link.replace("/resources/", "").replace(".html", "")
        assert slug in keep_slugs, f"Related link {slug} must be a keep resource article"

    # Off-topic checks
    rg_text = rg_match.group(1).lower()
    for off_topic in ["spotify wrapped", "kissing cousins", "sludge metal", "medical bills", "length at 12 months"]:
        assert off_topic not in rg_text, f"Off-topic '{off_topic}' found in Related Guides"

    # No regression to CTAs and interactive elements
    assert "data-cta" in text, "Article CTA markup must be preserved"
    assert "snugs-sticky-cta" in text, "Sticky mobile CTA must be preserved"
    assert 'aria-label="About the author"' in text, "Author section must be preserved"
    assert 'aria-label="Continue reading"' in text, "Continue reading section must be preserved"


def test_every_resource_article_breadcrumbs():
    """Verify breadcrumb and JSON-LD for every resource article."""
    articles = get_all_article_files()
    assert len(articles) >= 420, f"Expected ~428 article files, found {len(articles)}"

    for file_path, text in articles:
        title_match = re.search(r"<title>(.*?)</title>", text)
        assert title_match, f"Missing title in {file_path.name}"
        article_title = title_match.group(1).replace(" | Snugs.ai", "").strip()

        # Visible nav
        nav_match = re.search(r'<nav class="text-sm text-gray-600 mb-6 animate-fadeIn">(.*?)</nav>', text, re.S)
        assert nav_match, f"Missing breadcrumb nav in {file_path.name}"
        nav_html = nav_match.group(1)

        last_crumb_match = re.search(r'<span class="text-gray-800">(.*?)</span>', nav_html, re.S)
        assert last_crumb_match, f"Missing last crumb span in {file_path.name}"
        last_crumb_text = html.unescape(last_crumb_match.group(1).strip())
        assert last_crumb_text == article_title, (
            f"Breadcrumb mismatch in {file_path.name}: '{last_crumb_text}' != '{article_title}'"
        )

        # JSON-LD BreadcrumbList item 3
        item3_match = re.search(
            r'\{\s*"@type":\s*"ListItem",\s*"position":\s*3,\s*"name":\s*(.*?),\s*"item":\s*"([^"]*)"\s*\}',
            text,
            re.S
        )
        assert item3_match, f"Missing BreadcrumbList item 3 in {file_path.name}"
        item3_name = json.loads(item3_match.group(1).strip())
        assert item3_name == article_title, (
            f"JSON-LD pos 3 mismatch in {file_path.name}: '{item3_name}' != '{article_title}'"
        )
        expected_url = f"https://snugs.ai/resources/{file_path.name}"
        assert item3_match.group(2).strip() == expected_url, (
            f"JSON-LD pos 3 URL mismatch in {file_path.name}"
        )


def test_no_leftover_howto_schema():
    """Verify HowTo 'Calm a Crying Baby' is only on calm-a-crying-baby.html."""
    articles = get_all_article_files()
    for file_path, text in articles:
        if file_path.name == "calm-a-crying-baby.html":
            assert '"@type": "HowTo"' in text or '"@type":"HowTo"' in text
            assert "Calm a Crying Baby" in text
        else:
            scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)
            for s in scripts:
                assert '"@type": "HowTo"' not in s and '"@type":"HowTo"' not in s, (
                    f"Leftover HowTo schema found in {file_path.name}"
                )


def test_every_resource_article_related_guides():
    """Verify Related Guides section across all articles is small, unique, and on-topic."""
    articles = get_all_article_files()
    keep_slugs = get_keep_resource_slugs()

    for file_path, text in articles:
        slug = file_path.stem
        rg_match = re.search(
            r'<section class="mt-10 pt-8 border-t-2 border-orange-100">\s*<h2[^>]*>Related Guides</h2>\s*<ul[^>]*>(.*?)</ul>\s*</section>',
            text,
            re.S
        )
        assert rg_match, f"Missing Related Guides section in {file_path.name}"
        rg_links = re.findall(r'href="(/resources/[^"]+\.html)"', rg_match.group(1))

        # 5 to 12 links
        assert 5 <= len(rg_links) <= 12, (
            f"Related Guides link count in {file_path.name} out of bounds: {len(rg_links)}"
        )
        # Unique links
        assert len(rg_links) == len(set(rg_links)), f"Duplicate links in {file_path.name}"
        # No self link
        assert f"/resources/{file_path.name}" not in rg_links, f"Self link in {file_path.name}"

        # All point to valid keep resource articles
        for link in rg_links:
            target_slug = link.replace("/resources/", "").replace(".html", "")
            assert target_slug in keep_slugs, (
                f"Link to non-keep resource in {file_path.name}: {target_slug}"
            )


def test_sitemap_article_urls_crawl():
    """Crawl sitemap article URLs and verify none have the all-resources dump."""
    sitemap_path = BASE / "sitemap.xml"
    assert sitemap_path.exists(), "sitemap.xml must exist"
    tree = ElementTree.parse(sitemap_path)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text.strip() for e in tree.getroot().findall("s:url/s:loc", ns)]

    article_urls = [
        loc for loc in locs
        if "/resources/" in loc and loc.endswith(".html") and not loc.endswith("/index.html")
    ]
    assert len(article_urls) >= 120, f"Expected >=120 resource articles in sitemap, got {len(article_urls)}"

    for url in article_urls:
        rel_path = url.replace("https://snugs.ai/", "")
        local_file = BASE / rel_path
        assert local_file.exists(), f"File {rel_path} for sitemap URL {url} does not exist"
        text = local_file.read_text(encoding="utf-8")

        rg_match = re.search(
            r'<section class="mt-10 pt-8 border-t-2 border-orange-100">\s*<h2[^>]*>Related Guides</h2>\s*<ul[^>]*>(.*?)</ul>\s*</section>',
            text,
            re.S
        )
        assert rg_match, f"Sitemap article {rel_path} missing Related Guides"
        rg_links = re.findall(r'href="(/resources/[^"]+\.html)"', rg_match.group(1))

        assert 5 <= len(rg_links) <= 12, (
            f"Sitemap article {rel_path} has {len(rg_links)} related links (dump not cleaned)"
        )


def test_ctas_and_interactive_elements_intact():
    """Verify article CTAs and sticky mobile CTA are not regressed across sample articles."""
    articles = get_all_article_files()
    sample_files = articles[:20] + articles[-20:]

    for file_path, text in sample_files:
        assert "data-cta" in text, f"Missing data-cta in {file_path.name}"
        assert "snugs-sticky-cta" in text, f"Missing snugs-sticky-cta in {file_path.name}"
