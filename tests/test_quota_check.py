import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

import quota_check as quota


class QuotaCheckTests(unittest.TestCase):
    def test_limited_and_unlimited_token_results(self):
        limited = quota.normalize_token({"code": True, "data": {
            "total_available": 250000, "total_used": 750000, "total_granted": 1000000,
            "unlimited_quota": False, "user_quota": {"total_available": 1250000},
        }}, 500000)
        self.assertEqual((limited["remaining"], limited["account_remaining"], limited["used"]), (.5, 2.5, 1.5))
        unlimited = quota.normalize_token({"code": True, "data": {
            "total_available": -762481185, "unlimited_quota": True,
        }}, 500000)
        self.assertIsNone(unlimited["remaining"])
        self.assertTrue(unlimited["unlimited"])

    def test_fetch_uses_gateway_units_and_separate_account_token(self):
        calls = []
        def fake_get(url, headers=None):
            calls.append((url, headers))
            if url.endswith("/api/status"):
                return {"data": {"quota_per_unit": 100000}}
            if url.endswith("/api/usage/token/"):
                return {"code": True, "data": {"total_available": 250000, "unlimited_quota": False}}
            return {"success": True, "data": {"quota": 125000}}
        result = quota.fetch("https://gateway.example/", "api-demo", "account-demo", "42", get=fake_get)
        self.assertEqual(result["remaining"], 2.5)
        self.assertEqual(result["account_remaining"], 1.25)
        self.assertEqual([url for url, _ in calls], [
            "https://gateway.example/api/status", "https://gateway.example/api/usage/token/", "https://gateway.example/api/user/self"])
        self.assertEqual(calls[1][1]["Authorization"], "Bearer api-demo")
        self.assertEqual(calls[2][1]["Authorization"], "Bearer account-demo")
        self.assertEqual(calls[2][1]["New-Api-User"], "42")

    def test_invalid_balances_and_credentials_fail(self):
        with self.assertRaises(ValueError):
            quota.normalize_token({"code": True, "data": {"total_available": True}}, 500000)
        with self.assertRaises(ValueError):
            quota.normalize_token([], 500000)
        with self.assertRaises(ValueError):
            quota.normalize_account({"success": True, "data": {"quota": float("nan")}}, 500000)
        with self.assertRaises(ValueError):
            quota.normalize_account({"success": False, "data": {"quota": 1}}, 500000)
        with self.assertRaises(ValueError):
            quota.fetch("https://gateway.example", "api-demo", "account-demo", None)
        with self.assertRaises(ValueError):
            quota.fetch("https://gateway.example", "api-demo", "account-demo", "not-a-number")
        for url in ("http://gateway.example", "https://name:pass@gateway.example", "https://gateway.example/path"):
            with self.assertRaises(ValueError):
                quota.gateway_url(url)
        self.assertEqual(quota.gateway_url("http://localhost:3000"), "http://localhost:3000")

    def test_cli_json_exposes_only_quota_fields(self):
        output = io.StringIO()
        response = {"unlimited": False, "remaining": 1.25, "account_remaining": None,
                    "used": None, "granted": None, "expires_at": None}
        with patch.dict(os.environ, {"GATEWAY_API_KEY": "private-demo"}), patch.object(quota, "fetch", return_value=response), contextlib.redirect_stdout(output):
            self.assertEqual(quota.main(["--base-url", "https://gateway.example", "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue()), response)
        self.assertNotIn("private-demo", output.getvalue())


if __name__ == "__main__":
    unittest.main()
