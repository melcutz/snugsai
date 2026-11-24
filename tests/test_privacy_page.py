"""Tests for snugs.ai/privacy.html (refs snugs-ai#175, snugs-ai#194, snugs-ai#190, snugsai#49)."""

from pathlib import Path
import re

BASE = Path(__file__).resolve().parent.parent

EXACT_DELETION_SENTENCE = (
    "Delete your account in Settings > Delete account, or email privacy@snugs.ai (see Data Retention)"
)

APPROVED_DATA_RETENTION_PARAGRAPH = (
    "We keep your data while your account is active. "
    "To delete your account, use Settings > Delete account, or email privacy@snugs.ai from the address you signed up with. "
    "Deleting cancels any active subscription and permanently deletes your account, baby profiles, chats and log entries within 30 days. "
    "Payment records held by our payment processor are kept as required for tax and accounting, and backups and service logs expire on their own schedule."
)


def test_privacy_page_access_email():
    """Verify Access choice uses privacy@snugs.ai and not contact@snugs.ai."""
    privacy_html = BASE / "privacy.html"
    assert privacy_html.exists(), "privacy.html must exist"
    content = privacy_html.read_text(encoding="utf-8")

    # privacy@snugs.ai must be present in privacy.html
    assert "privacy@snugs.ai" in content

    # Access line must link to privacy@snugs.ai
    access_match = re.search(
        r'<li><strong>Access</strong>:\s*You can request access to your information by emailing <a href="mailto:([^"]+)">([^<]+)</a>\.</li>',
        content,
    )
    assert access_match, "Access line not found with expected structure"
    href_email, text_email = access_match.groups()
    assert href_email == "privacy@snugs.ai"
    assert text_email == "privacy@snugs.ai"


def test_privacy_page_deletion_choice():
    """Verify Deletion choice includes verbatim self-serve instruction."""
    privacy_html = BASE / "privacy.html"
    content = privacy_html.read_text(encoding="utf-8")

    assert EXACT_DELETION_SENTENCE in content
    assert "Delete your account in Settings > Delete account, or email privacy@snugs.ai (see Data Retention)" in content


def test_privacy_page_other_contacts_retained():
    """Verify newsletter unsubscribe and general policy inquiries use privacy@snugs.ai."""
    privacy_html = BASE / "privacy.html"
    content = privacy_html.read_text(encoding="utf-8")

    # Free Baby Stuff Weekly newsletter unsubscribe email uses privacy@snugs.ai
    assert (
        'or by emailing <a href="mailto:privacy@snugs.ai">privacy@snugs.ai</a>'
        in content
    )

    # General questions about this Policy contact uses privacy@snugs.ai
    assert (
        'If you have questions about this Policy or our practices, contact us at <a href="mailto:privacy@snugs.ai">privacy@snugs.ai</a>'
        in content
    )


def test_privacy_page_no_contact_email():
    """Verify contact@snugs.ai is completely absent from privacy.html."""
    privacy_html = BASE / "privacy.html"
    content = privacy_html.read_text(encoding="utf-8")
    assert "contact@snugs.ai" not in content


def test_privacy_page_data_retention_approved_paragraph():
    """Verify approved Data Retention paragraph appears verbatim and reasonable efforts is removed."""
    privacy_html = BASE / "privacy.html"
    content = privacy_html.read_text(encoding="utf-8")

    # Approved paragraph must appear verbatim
    assert APPROVED_DATA_RETENTION_PARAGRAPH in content

    # Verbatim self-serve deletion sentences must be present
    assert (
        "To delete your account, use Settings > Delete account, or email privacy@snugs.ai from the address you signed up with."
        in content
    )
    assert (
        "Deleting cancels any active subscription and permanently deletes your account, baby profiles, chats and log entries within 30 days."
        in content
    )

    # "reasonable efforts" must not be used as the deletion promise
    assert "reasonable efforts" not in content

    # Old email-only Data Retention sentences must not be present
    old = (
        "To delete your account, email privacy@snugs.ai from the address you signed up with. "
        "We'll confirm, cancel any active subscription, and permanently delete your account, "
        "baby profiles, chats and log entries within 30 days."
    )
    assert old not in content


def test_privacy_page_effective_date():
    """Verify effective date is updated to November 23, 2026."""
    privacy_html = BASE / "privacy.html"
    content = privacy_html.read_text(encoding="utf-8")

    assert "November 23, 2026" in content
    assert "October 11, 2026" not in content
    assert "Effective date: November 23, 2026" in content
