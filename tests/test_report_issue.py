"""Tests for the report_skill_issue CLI and body/sanitization logic."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import report_skill_issue  # noqa: E402


class ScrubTests(unittest.TestCase):
    def test_scrubs_mcp_urls(self):
        text = "failed at https://foo.zohomcp.eu/mcp/deadbeef1234/message during call"
        cleaned = report_skill_issue.scrub(text)
        self.assertNotIn("deadbeef1234", cleaned)
        self.assertIn("[REDACTED_MCP_URL]", cleaned)

    def test_scrubs_email_addresses(self):
        text = "user test.user@example.com reported failure"
        cleaned = report_skill_issue.scrub(text)
        self.assertNotIn("test.user@example.com", cleaned)
        self.assertIn("[REDACTED_EMAIL]", cleaned)

    def test_scrubs_long_numeric_ids(self):
        text = "record id 81839000025937307 failed"
        cleaned = report_skill_issue.scrub(text)
        self.assertNotIn("81839000025937307", cleaned)
        self.assertIn("[REDACTED_ID]", cleaned)

    def test_scrubs_auth_tokens(self):
        text = "header Authorization: Bearer abc123def456 passed"
        cleaned = report_skill_issue.scrub(text)
        self.assertNotIn("abc123def456", cleaned)


class ParserTests(unittest.TestCase):
    def test_help_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            report_skill_issue.build_parser().parse_args(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_requires_title_and_kind(self):
        with self.assertRaises(SystemExit) as ctx:
            report_skill_issue.build_parser().parse_args([])
        self.assertEqual(ctx.exception.code, 2)

    def test_rejects_unknown_kind(self):
        with self.assertRaises(SystemExit) as ctx:
            report_skill_issue.build_parser().parse_args(
                ["--title", "foo", "--kind", "not-a-kind"]
            )
        self.assertEqual(ctx.exception.code, 2)

    def test_dry_run_renders_body_without_network(self):
        args = report_skill_issue.build_parser().parse_args(
            [
                "--title",
                "helper crash",
                "--kind",
                "helper-bug",
                "--expected",
                "returns rows",
                "--actual",
                "TypeError",
                "--module",
                "Deals",
                "--repro",
                "run search_records.py with https://x.zohomcp.eu/mcp/t/message",
                "--dry-run",
            ]
        )
        body = report_skill_issue.build_body(args)
        self.assertIn("### Kind\nhelper-bug", body)
        self.assertIn("### Expected\nreturns rows", body)
        self.assertIn("### Module\nDeals", body)
        self.assertIn("[REDACTED_MCP_URL]", body)


class MainFlowTests(unittest.TestCase):
    def test_dry_run_exits_zero(self):
        code = report_skill_issue.main(
            ["--title", "bug", "--kind", "helper-bug", "--dry-run"]
        )
        self.assertEqual(code, 0)

    def test_existing_issue_returns_existing_url(self):
        with mock.patch.object(
            report_skill_issue,
            "find_existing",
            return_value={"number": 1, "title": "bug", "url": "https://github.com/foo/bar/issues/1"},
        ):
            code = report_skill_issue.main(
                ["--title", "bug", "--kind", "helper-bug"]
            )
        self.assertEqual(code, 0)

    def test_create_failure_returns_one(self):
        with mock.patch.object(report_skill_issue, "find_existing", return_value=None):
            with mock.patch.object(
                report_skill_issue,
                "create_issue",
                return_value=(1, "", "permission denied"),
            ):
                code = report_skill_issue.main(
                    ["--title", "bug", "--kind", "helper-bug"]
                )
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
