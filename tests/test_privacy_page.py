"""Tests for snugs.ai/privacy.html (refs snugs-ai#175)."""

from pathlib import Path
import re

BASE = Path(__file__).resolve().parent.parent


def test_privacy_page_access_deletion_email():
    """Verify Access/Deletion uses privacy@snugs.ai and not contact@snugs.ai."""
    privacy_html = BASE / "privacy.html"
    assert privacy_html.exists(), "privacy.html must exist"
    content = privacy_html.read_text(encoding="utf-8")

    # privacy@snugs.ai must be present in privacy.html
    assert "privacy@snugs.ai" in content

    # Access/Deletion line must link to privacy@snugs.ai
    access_deletion_match = re.search(
        r'<li><strong>Access/Deletion</strong>:\s*You can request access to or deletion of your information by emailing <a href="mailto:([^"]+)">([^<]+)</a>\.</li>',
        content,
    )
    assert access_deletion_match, "Access/Deletion line not found with expected structure"
    href_email, text_email = access_deletion_match.groups()
    assert href_email == "privacy@snugs.ai"
    assert text_email == "privacy@snugs.ai"


def test_privacy_page_other_contacts_retained():
    """Verify newsletter unsubscribe and general policy inquiries retain contact@snugs.ai."""
    privacy_html = BASE / "privacy.html"
    content = privacy_html.read_text(encoding="utf-8")

    # Free Baby Stuff Weekly newsletter unsubscribe email stays contact@snugs.ai
    assert "or by emailing <a href=\"mailto:contact@snugs.ai\">contact@snugs.ai</a>" in content

    # General questions about this Policy contact stays contact@snugs.ai
    assert "If you have questions about this Policy or our practices, contact us at <a href=\"mailto:contact@snugs.ai\">contact@snugs.ai</a>" in content
