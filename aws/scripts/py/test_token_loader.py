"""Exercise the real shell loader with synthetic secrets and a stubbed AWS CLI."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

LOADER = Path(__file__).resolve().parents[1] / "sh" / "retrieve_token.sh"
HARNESS = r"""
set -euo pipefail
source "$1"
"$2" -c 'import json, os; assert os.environ["GITHUB_TOKEN"] == json.loads(os.environ["SYNTHETIC_EXPECTED_TOKEN_JSON"])'
echo 'Child received exact token'
"""
AWS_STUB = r"""
import json, os, sys, time
from pathlib import Path
trace = Path(os.environ["SYNTHETIC_TRACE"])
calls = json.loads(trace.read_text()) if trace.exists() else []
operation = sys.argv[2]
previous_reads = sum(call["operation"] == "get-secret-value" for call in calls)
calls.append({
    "operation": operation,
    "arguments": sys.argv[1:],
    "attempts": os.environ.get("AWS_MAX_ATTEMPTS"),
    "retry_mode": os.environ.get("AWS_RETRY_MODE"),
    "inherited_token": os.environ.get("GITHUB_TOKEN"),
})
trace.write_text(json.dumps(calls))
if operation == os.environ.get("SYNTHETIC_FAIL"):
    print("synthetic-sensitive-response", file=sys.stderr)
    print("synthetic-sensitive-response")
    sys.exit(254)
if operation == os.environ.get("SYNTHETIC_SLOW"):
    time.sleep(10)
if operation == "list-secrets":
    print("crm-github-token-synthetic")
elif operation == "get-secret-value":
    secrets = json.loads(os.environ["SYNTHETIC_SECRETS"])
    secret = secrets[min(previous_reads, len(secrets) - 1)]
    print(secret if isinstance(secret, str) else json.dumps(secret))
else:
    sys.exit(99)
"""


class TokenLoaderTests(unittest.TestCase):
    def run_loader(self, secret, *, sequence=None, settings=None, trace_shell=False):
        # Do not inherit credentials or a pre-exported GITHUB_TOKEN from the host.
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / "aws"
            stub.write_text(f"#!{sys.executable}\n{AWS_STUB}")
            stub.chmod(0o755)
            trace = Path(directory) / "calls.json"
            env = {
                "PATH": directory + os.pathsep + os.environ.get("PATH", os.defpath),
                "AWS_DEFAULT_REGION": "eu-central-1",
                "SYNTHETIC_SECRETS": json.dumps(sequence or [secret]),
                "SYNTHETIC_EXPECTED_TOKEN_JSON": json.dumps(
                    secret.get("token", "") if isinstance(secret, dict) else ""
                ),
                "SYNTHETIC_TRACE": str(trace),
                **(settings or {}),
            }
            start = time.monotonic()
            result = subprocess.run(
                [
                    "bash",
                    "--noprofile",
                    "--norc",
                    "-xc" if trace_shell else "-c",
                    HARNESS,
                    "token-test",
                    str(LOADER),
                    sys.executable,
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            result.elapsed = time.monotonic() - start
            result.calls = json.loads(trace.read_text()) if trace.exists() else []
            return result

    def freshness(self, **overrides):
        return {
            "GITHUB_TOKEN_WAIT_SECONDS": "3",
            "GITHUB_TOKEN_MIN_TTL_SECONDS": "900",
            "GITHUB_TOKEN_POLL_SECONDS": "1",
            **overrides,
        }

    def test_long_installation_token_is_exported_unchanged(self):
        token = "ghs_" + "x" * 373
        result = self.run_loader({"token": token, "expires_at": "2099-01-01T00:00:00Z"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Child received exact token", result.stdout)
        self.assertNotIn(token, result.stdout + result.stderr)

    def test_opaque_tokens_have_no_prefix_or_length_requirement(self):
        for token in ["x", "synthetic.v2_token-+/=", "null"]:
            with self.subTest(token=token):
                result = self.run_loader({"token": token})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Child received exact token", result.stdout)

    def test_missing_null_nonstring_and_empty_tokens_are_rejected(self):
        secrets = [{}, *({"token": value} for value in [None, 123, True, [], {}, ""])]
        for secret in secrets:
            with self.subTest(secret=secret):
                result = self.run_loader(secret)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("nonempty string", result.stdout)
                self.assertNotIn("Child received exact token", result.stdout)

    def test_whitespace_and_control_characters_are_rejected_before_extraction(self):
        for token in [
            " ",
            "\t\n",
            " synthetic",
            "synthetic ",
            "syn thetic",
            "synthetic\n",
            "syn\tthetic",
            "syn\x00thetic",
        ]:
            with self.subTest(token=repr(token)):
                result = self.run_loader({"token": token})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("nonempty string", result.stdout)
                self.assertNotIn("Child received exact token", result.stdout)

    def test_expired_token_is_rejected(self):
        result = self.run_loader(
            {"token": "synthetic-token", "expires_at": "2000-01-01T00:00:00Z"}
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GitHub token has expired", result.stdout)
        self.assertNotIn("Child received exact token", result.stdout)

    def test_expired_then_fresh_exports_only_final_exact_token(self):
        fresh = {"token": "opaque." + "x" * 373, "expires_at": "2099-01-01T00:00:00Z"}
        result = self.run_loader(
            fresh,
            sequence=[
                {"token": "synthetic-expired", "expires_at": "2000-01-01T00:00:00Z"},
                fresh,
            ],
            settings=self.freshness(GITHUB_TOKEN="synthetic-inherited"),
            trace_shell=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Child received exact token", result.stdout)
        self.assertEqual(len(result.calls), 4)
        for call in result.calls:
            self.assertIsNone(call["inherited_token"])
            self.assertEqual(call["attempts"], "1")
            self.assertEqual(call["retry_mode"], "standard")
            for flag in ("--cli-connect-timeout", "--cli-read-timeout"):
                limit = int(call["arguments"][call["arguments"].index(flag) + 1])
                self.assertGreaterEqual(limit, 1)
                self.assertLessEqual(limit, 3)
        for token in (fresh["token"], "synthetic-expired", "synthetic-inherited"):
            self.assertNotIn(token, result.stdout + result.stderr)

    def test_expired_token_stops_at_deadline_without_extra_poll(self):
        result = self.run_loader(
            {"token": "synthetic-expired", "expires_at": "2000-01-01T00:00:00Z"},
            settings=self.freshness(
                GITHUB_TOKEN_WAIT_SECONDS="1", GITHUB_TOKEN_POLL_SECONDS="15"
            ),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Timed out", result.stdout)
        self.assertEqual(len(result.calls), 2)
        self.assertLess(result.elapsed, 3)
        self.assertNotIn("Child received exact token", result.stdout)

    def test_near_expiry_is_not_accepted(self):
        expiry = datetime.now(timezone.utc) + timedelta(seconds=600)
        result = self.run_loader(
            {"token": "synthetic-near-expiry", "expires_at": expiry.isoformat()},
            settings=self.freshness(GITHUB_TOKEN_WAIT_SECONDS="1"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Timed out", result.stdout)
        self.assertNotIn("Child received exact token", result.stdout)

    def test_missing_expiry_is_rejected_only_in_freshness_mode(self):
        for expiry in (None, ""):
            with self.subTest(expiry=expiry):
                result = self.run_loader(
                    {"token": "synthetic-token", "expires_at": expiry},
                    settings=self.freshness(),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("expiration time is required", result.stdout)
                self.assertEqual(len(result.calls), 2)

    def test_malformed_expiry_fails_promptly_without_logging_value(self):
        for expiry in (
            "synthetic-sensitive-expiry",
            "2099-01-01T00:00:00",
            "2099-99-01T00:00:00Z",
            "2099-01-01T00:00:00Z\n",
            123,
            [],
            {},
        ):
            with self.subTest(expiry=expiry):
                result = self.run_loader(
                    {"token": "synthetic-sensitive-token", "expires_at": expiry},
                    settings=self.freshness(),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Invalid GitHub token expiration", result.stdout)
                self.assertEqual(len(result.calls), 2)
                self.assertNotIn("synthetic-sensitive", result.stdout + result.stderr)

    def test_malformed_json_and_token_fail_without_retry(self):
        for secret in (
            "synthetic-sensitive-invalid-json",
            '{"token":"synthetic-sensitive-one"}\n{"token":"synthetic-sensitive-two"}',
            {"token": []},
            [],
        ):
            with self.subTest(secret=secret):
                result = self.run_loader(secret, settings=self.freshness())
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(result.calls), 2)
                self.assertNotIn("synthetic-sensitive", result.stdout + result.stderr)

    def test_denied_access_fails_promptly_and_suppresses_raw_response(self):
        for operation, count in (("list-secrets", 1), ("get-secret-value", 2)):
            with self.subTest(operation=operation):
                result = self.run_loader(
                    {"token": "synthetic-token"},
                    settings=self.freshness(SYNTHETIC_FAIL=operation),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(result.calls), count)
                self.assertNotIn(
                    "synthetic-sensitive-response", result.stdout + result.stderr
                )
                self.assertNotIn("Child received exact token", result.stdout)

    def test_hung_cli_is_killed_within_remaining_deadline(self):
        for operation in ("list-secrets", "get-secret-value"):
            with self.subTest(operation=operation):
                result = self.run_loader(
                    {"token": "synthetic-token"},
                    settings=self.freshness(
                        GITHUB_TOKEN_WAIT_SECONDS="1", SYNTHETIC_SLOW=operation
                    ),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("time limit", result.stdout)
                self.assertLess(result.elapsed, 3)
                self.assertNotIn("Child received exact token", result.stdout)

    def test_invalid_limits_fail_before_aws(self):
        for name, values in {
            "GITHUB_TOKEN_WAIT_SECONDS": (
                "",
                "-1",
                "1.5",
                "01",
                "3601",
                "999999999999",
            ),
            "GITHUB_TOKEN_MIN_TTL_SECONDS": ("-1", "abc", "3601", "$(false)"),
            "GITHUB_TOKEN_POLL_SECONDS": ("0", "-1", "301", "1+1"),
        }.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    result = self.run_loader(
                        {"token": "synthetic-token"},
                        settings=self.freshness(**{name: value}),
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(
                        "Invalid GitHub token freshness limits", result.stdout
                    )
                    self.assertEqual(result.calls, [])


if __name__ == "__main__":
    unittest.main()
