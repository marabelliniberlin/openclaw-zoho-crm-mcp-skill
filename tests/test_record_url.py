"""Credential-free unit tests for scripts/record_url.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "scripts" / "record_url.py"


def load_record_url_module():
    spec = importlib.util.spec_from_file_location("record_url_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RecordUrlCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record_url = load_record_url_module()

    def run_script(self, *arguments):
        env = os.environ.copy()
        env.pop("ZOHO_MCP_URL", None)
        env.pop("ZOHO_CRM_MCP_URL", None)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def test_help_does_not_require_credentials_or_make_a_request(self):
        result = self.run_script("--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_unknown_and_missing_arguments_use_argparse_exit_code_2(self):
        cases = (
            (),
            ("Leads",),
            ("Leads", "not-a-number"),
            ("Leads", "123", "--dc", "invalid-dc"),
            ("Leads", "123", "--unknown"),
        )

        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = self.run_script(*arguments)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage:", result.stderr)

    def test_plain_output_resolves_zgid_and_tab_name(self):
        calls = []

        def fake_mcporter_call(tool, arguments, timeout=30):
            calls.append((tool, arguments, timeout))
            if tool == "ZohoCRM_getOrganization":
                return {
                    "data": {
                        "org": [
                            {
                                "company_name": "Acme",
                                "zgid": "20079833178",
                            }
                        ]
                    }
                }
            if tool == "ZohoCRM_getModules":
                return {
                    "data": {
                        "modules": [
                            {"api_name": "Leads", "module_name": "Leads"},
                            {"api_name": "Events", "module_name": "Meetings"},
                            {"api_name": "vServer", "module_name": "CustomModule3"},
                        ]
                    }
                }
            raise AssertionError(f"unexpected tool: {tool}")

        stdout = io.StringIO()
        with patch.object(self.record_url, "mcporter_call", side_effect=fake_mcporter_call):
            with contextlib.redirect_stdout(stdout):
                exit_code = self.record_url.main(["Leads", "407625000068467001"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "ZohoCRM_getOrganization")
        self.assertEqual(calls[0][1], {})
        self.assertEqual(calls[1][0], "ZohoCRM_getModules")
        self.assertEqual(calls[1][1], {})  # parameter-free call
        self.assertEqual(
            stdout.getvalue().strip(),
            "https://crm.zoho.eu/crm/org20079833178/tab/Leads/407625000068467001",
        )

    def test_maps_divergent_module_names_and_supports_dc_and_json(self):
        def fake_mcporter_call(tool, arguments, timeout=30):
            if tool == "ZohoCRM_getOrganization":
                return {"org": [{"zgid": "987654321"}]}
            if tool == "ZohoCRM_getModules":
                return {
                    "modules": [
                        {"api_name": "Events", "module_name": "Meetings"},
                        {"api_name": "Sales_Orders", "module_name": "SalesOrders"},
                    ]
                }
            raise AssertionError(f"unexpected tool: {tool}")

        stdout = io.StringIO()
        with patch.object(self.record_url, "mcporter_call", side_effect=fake_mcporter_call):
            with contextlib.redirect_stdout(stdout):
                exit_code = self.record_url.main(
                    ["Events", "123456789", "--dc", "com", "--json"]
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(
            payload,
            {
                "url": "https://crm.zoho.com/crm/org987654321/tab/Meetings/123456789",
                "zgid": "987654321",
                "module": "Events",
                "tab_name": "Meetings",
                "record_id": "123456789",
            },
        )

    def test_missing_module_returns_exit_code_one(self):
        def fake_mcporter_call(tool, arguments, timeout=30):
            if tool == "ZohoCRM_getOrganization":
                return {"org": [{"zgid": "123"}]}
            if tool == "ZohoCRM_getModules":
                return {"modules": [{"api_name": "Leads", "module_name": "Leads"}]}
            raise AssertionError(f"unexpected tool: {tool}")

        stderr = io.StringIO()
        with patch.object(self.record_url, "mcporter_call", side_effect=fake_mcporter_call):
            with contextlib.redirect_stderr(stderr):
                exit_code = self.record_url.main(["NonExistent", "123"])

        self.assertEqual(exit_code, 1)
        self.assertIn("not found in getModules", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
