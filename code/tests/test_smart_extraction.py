"""Test smart section extraction from documents."""

import sys
import importlib.util
from pathlib import Path

# Import smart_extraction directly (avoid embeddings/__init__.py dependency on sentence_transformers)
spec = importlib.util.spec_from_file_location(
    "smart_extraction",
    Path(__file__).parent.parent / "embeddings" / "smart_extraction.py"
)
smart_extraction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smart_extraction)

SmartExtractor = smart_extraction.SmartExtractor
extract_relevant_content = smart_extraction.extract_relevant_content


SAMPLE_DOC = """---
title: "Account Management"
source_url: "https://support.example.com/account"
article_id: "12345"
---

# Account Management

## How to Create an Account

To create an account, follow these steps:

1. Visit our website homepage
2. Click the "Sign Up" button in the top right
3. Enter your email address
4. Create a strong password (minimum 8 characters)
5. Verify your email by clicking the link we send you
6. You're all set!

## How to Reset Your Password

If you forgot your password, here's what to do:

1. Go to the login page
2. Click "Forgot Password?" link
3. Enter your email address
4. Check your email for a password reset link
5. Click the link in your email
6. Enter your new password
7. Confirm the new password
8. You can now login with your new password

## Account Security Tips

Keep your account secure with these best practices:

- Enable two-factor authentication in your settings
- Use a strong, unique password
- Never share your password with anyone
- Review your login activity regularly
- Logout from other devices when you're done
- Change your password if you suspect unauthorized access

## Deleting Your Account

To permanently delete your account:

1. Go to Settings
2. Click on "Account" tab
3. Scroll to the bottom of the page
4. Click "Delete Account"
5. Confirm deletion (this action cannot be undone)
6. Your data will be removed within 30 days
"""


class TestSmartExtraction:
    """Test SmartExtractor functionality."""

    def test_parse_yaml_front_matter(self):
        """Test parsing YAML front matter."""
        extractor = SmartExtractor()
        metadata, body = extractor.parse_yaml_front_matter(SAMPLE_DOC)

        assert metadata.get("title") == "Account Management"
        assert metadata.get("source_url") == "https://support.example.com/account"
        assert len(body) > 0
        assert "## How to Create" in body
        print("✅ test_parse_yaml_front_matter PASSED")

    def test_split_into_sections(self):
        """Test splitting document into sections."""
        extractor = SmartExtractor()
        _, body = extractor.parse_yaml_front_matter(SAMPLE_DOC)
        sections = extractor.split_into_sections(body)

        assert len(sections) == 4
        assert "Create" in sections[0][0]
        assert "Reset" in sections[1][0]
        assert "Security" in sections[2][0]
        assert "Deleting" in sections[3][0]
        print("✅ test_split_into_sections PASSED")

    def test_score_section_reset_password(self):
        """Test scoring sections for password reset query."""
        extractor = SmartExtractor()
        _, body = extractor.parse_yaml_front_matter(SAMPLE_DOC)
        sections = extractor.split_into_sections(body)

        query = "forgot my password"
        scores = [
            (header, extractor.score_section(header, content, query))
            for header, content in sections
        ]

        # Reset Password section should have highest score
        reset_section = [s for s in scores if "Reset" in s[0]][0]
        others = [s for s in scores if "Reset" not in s[0]]

        assert reset_section[1] > max([s[1] for s in others])
        print(f"✅ test_score_section_reset_password PASSED (reset score: {reset_section[1]:.2f})")

    def test_score_section_delete_account(self):
        """Test scoring sections for delete account query."""
        extractor = SmartExtractor()
        _, body = extractor.parse_yaml_front_matter(SAMPLE_DOC)
        sections = extractor.split_into_sections(body)

        query = "delete my account"
        scores = [
            (header, extractor.score_section(header, content, query))
            for header, content in sections
        ]

        # Delete Account section should have highest score
        delete_section = [s for s in scores if "Deleting" in s[0]][0]
        others = [s for s in scores if "Deleting" not in s[0]]

        assert delete_section[1] > max([s[1] for s in others])
        print(f"✅ test_score_section_delete_account PASSED (delete score: {delete_section[1]:.2f})")

    def test_extract_relevant_section(self):
        """Test extracting relevant section."""
        extractor = SmartExtractor()

        result = extractor.extract_relevant_section(
            SAMPLE_DOC,
            "how do I reset password",
            max_chars=500
        )

        assert len(result) <= 500
        assert "Reset" in result or "reset" in result
        assert "Forgot" in result or "forgot" in result
        print(f"✅ test_extract_relevant_section PASSED ({len(result)} chars)")

    def test_extract_action_items(self):
        """Test extracting action items."""
        extractor = SmartExtractor()

        _, body = extractor.parse_yaml_front_matter(SAMPLE_DOC)
        sections = extractor.split_into_sections(body)

        # Get reset password section
        reset_section = [s[1] for s in sections if "Reset" in s[0]][0]

        items = extractor.extract_action_items(reset_section)

        assert len(items) > 0
        assert any("login" in item.lower() for item in items)
        assert any("email" in item.lower() for item in items)
        print(f"✅ test_extract_action_items PASSED (found {len(items)} items)")

    def test_condensed_output(self):
        """Test that output is properly condensed."""
        result = extract_relevant_content(
            SAMPLE_DOC,
            "I need to reset my password",
            max_chars=800
        )

        assert len(result) <= 800
        assert len(result) > 0
        # Should contain relevant information
        assert "password" in result.lower()
        print(f"✅ test_condensed_output PASSED ({len(result)} chars, < 800)")

    def test_multiple_queries(self):
        """Test extraction for multiple different queries."""
        extractor = SmartExtractor()

        test_cases = [
            ("forgot password", "reset"),
            ("delete account", "delete"),
            ("security", "secure"),
            ("create account", "create"),
        ]

        for query, expected_word in test_cases:
            result = extractor.extract_relevant_section(SAMPLE_DOC, query, max_chars=400)
            assert len(result) > 0
            assert len(result) <= 400
            print(f"  ✅ Query '{query}' -> {len(result)} chars")

        print("✅ test_multiple_queries PASSED")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("SMART EXTRACTION TEST SUITE")
    print("="*70 + "\n")

    test = TestSmartExtraction()

    tests = [
        test.test_parse_yaml_front_matter,
        test.test_split_into_sections,
        test.test_score_section_reset_password,
        test.test_score_section_delete_account,
        test.test_extract_relevant_section,
        test.test_extract_action_items,
        test.test_condensed_output,
        test.test_multiple_queries,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_func.__name__} FAILED: {str(e)}")
            failed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} ERROR: {str(e)}")
            failed += 1

    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
