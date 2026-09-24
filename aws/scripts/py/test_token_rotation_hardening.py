"""Offline execution tests for GitHub token rotation hardening.

The real shell script runs against a private temporary PATH.  Its commands are
small fakes, so no GitHub, AWS, clock service, private key, or token is used.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "aws/scripts/sh/rotate_github_token.sh"
SYNTHETIC_TOKEN = "synthetic-token-must-not-appear-in-output"
NEWEST_SECRET = "crm-github-token-newest-active"


class TokenRotationHardeningTests(unittest.TestCase):
    def run_rotation(
        self, expiration: str, *, http_failure: bool = False, selector_json=None
    ):
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory) / "bin"
            fake_bin.mkdir()
            put_log = Path(directory) / "put.log"
            self.write_fakes(fake_bin)
            environment = os.environ | {
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "AWS_REGION": "offline-test-region",
                "VILNACRM_APP_ID": "offline-app-id",
                "VILNACRM_APP_PRIVATE_KEY": "not-a-real-private-key",
                "FAKE_TOKEN": SYNTHETIC_TOKEN,
                "FAKE_SECRET_ID": NEWEST_SECRET,
                "FAKE_SELECTOR_JSON": (
                    selector_json
                    if selector_json is not None
                    else json.dumps(NEWEST_SECRET)
                ),
                "FAKE_EXPIRES_AT": expiration,
                "FAKE_HTTP_FAILURE": "1" if http_failure else "0",
                "FAKE_PUT_LOG": str(put_log),
            }
            result = subprocess.run(
                ["bash", "-x", str(SCRIPT)],
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                text=True,
                capture_output=True,
                check=False,
            )
            puts = put_log.read_text().splitlines() if put_log.exists() else []
        return result, puts

    def write_fakes(self, fake_bin: Path):
        scripts = {
            "python3": """#!/bin/sh
echo offline-jwt
""",
            "curl": """#!/bin/sh
for option in --fail --silent --show-error --max-time --retry; do
  case "$*" in *"$option"*) ;; *) echo 'missing curl hardening option' >&2; exit 2 ;; esac
done
case "$*" in *'--max-time 30'*'--retry 2'*) ;; *) echo 'wrong curl hardening value' >&2; exit 2 ;; esac
case "$*" in
  *access_tokens*)
    if [ "${FAKE_HTTP_FAILURE}" = 1 ]; then
      echo 'simulated HTTP failure' >&2
      exit 22
    fi
    printf '{"token":"%s","expires_at":"%s"}\\n' "$FAKE_TOKEN" "$FAKE_EXPIRES_AT"
    ;;
  *) printf '[{"id":123}]\\n' ;;
esac
""",
            "jq": """#!/bin/sh
input=$(cat)
case "$*" in
  *'.[0].id'*) printf '123\\n' ;;
  *'.token'*) printf '%s\\n' "$FAKE_TOKEN" ;;
  *'.expires_at'*) printf '%s\\n' "$FAKE_EXPIRES_AT" ;;
  *'length == 1'*'type == "string"'*)
    case "$input" in
      '"'"$FAKE_SECRET_ID"'"') printf '%s\\n' "$FAKE_SECRET_ID" ;;
      *) exit 1 ;;
    esac
    ;;
  *'-n'*)
    token=''
    expires_at=''
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --arg)
          [ "$#" -ge 3 ] || exit 2
          case "$2" in
            token) token=$3 ;;
            expires_at) expires_at=$3 ;;
          esac
          shift 3
          ;;
        *) shift ;;
      esac
    done
    [ "$token" = "$FAKE_TOKEN" ] || { echo 'unexpected token argument' >&2; exit 2; }
    [ "$expires_at" = "$FAKE_EXPIRES_AT" ] || { echo 'unexpected expiry argument' >&2; exit 2; }
    printf '{"token":"%s","expires_at":"%s"}\\n' "$token" "$expires_at"
    ;;
  *) exit 2 ;;
esac
""",
            "date": """#!/bin/sh
case "$*" in
  *'-d malformed'*) exit 1 ;;
  *'-d expired'*) printf '0\\n' ;;
  *'-d short'*) printf '2699\\n' ;;
  *'-d valid'*) printf '3600\\n' ;;
  *'-d 1970-01-01T01:00:00Z'*) printf '3600\\n' ;;
  *'+%s'*) printf '0\\n' ;;
  *) exit 2 ;;
esac
""",
            "aws": """#!/bin/sh
case "$*" in
  *'list-secrets'*'--output json'*)
    case "$*" in
      *sort_by*crm-github-token-*DeletedDate==null*) printf '%s\\n' "$FAKE_SELECTOR_JSON" ;;
      *) echo 'unexpected secret selector' >&2; exit 2 ;;
    esac
    ;;
  *'put-secret-value'*)
    secret_id=''
    secret_string=''
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --secret-id)
          [ "$#" -ge 2 ] || exit 2
          secret_id=$2
          shift 2
          ;;
        --secret-string)
          [ "$#" -ge 2 ] || exit 2
          secret_string=$2
          shift 2
          ;;
        *) shift ;;
      esac
    done
    [ "$secret_id" = "$FAKE_SECRET_ID" ] || { echo 'unexpected secret ID' >&2; exit 2; }
    expected=$(printf '{"token":"%s","expires_at":"%s"}' "$FAKE_TOKEN" "$FAKE_EXPIRES_AT")
    [ "$secret_string" = "$expected" ] || { echo 'unexpected secret payload' >&2; exit 2; }
    printf '%s\\n' "$secret_id" >> "$FAKE_PUT_LOG"
    ;;
  *) exit 2 ;;
esac
""",
        }
        for name, content in scripts.items():
            path = fake_bin / name
            path.write_text(textwrap.dedent(content))
            path.chmod(0o755)

    def assert_failure_without_put(self, expiration: str, message: str):
        result, puts = self.run_rotation(expiration)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stdout)
        self.assertEqual(puts, [])
        self.assertNotIn(SYNTHETIC_TOKEN, result.stdout + result.stderr)

    def test_malformed_expiration_does_not_write_secret(self):
        self.assert_failure_without_put(
            "malformed", "Invalid GitHub token expiration time"
        )

    def test_expired_expiration_does_not_write_secret(self):
        self.assert_failure_without_put("expired", "less than 45 minutes")

    def test_short_expiration_does_not_write_secret(self):
        self.assert_failure_without_put("short", "less than 45 minutes")

    def test_http_failure_does_not_write_secret(self):
        result, puts = self.run_rotation("valid", http_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("simulated HTTP failure", result.stderr)
        self.assertEqual(puts, [])
        self.assertNotIn(SYNTHETIC_TOKEN, result.stdout + result.stderr)

    def test_valid_token_writes_newest_active_secret_once_without_printing_token(self):
        result, puts = self.run_rotation("1970-01-01T01:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(puts, [NEWEST_SECRET])
        self.assertIn(f"Found secret: {NEWEST_SECRET}", result.stdout)
        self.assertNotIn(SYNTHETIC_TOKEN, result.stdout + result.stderr)

    def test_fake_writer_rejects_wrong_secret_or_token_without_logging(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory) / "bin"
            fake_bin.mkdir()
            self.write_fakes(fake_bin)
            put_log = Path(directory) / "put.log"
            environment = os.environ | {
                "FAKE_TOKEN": SYNTHETIC_TOKEN,
                "FAKE_EXPIRES_AT": "valid",
                "FAKE_SECRET_ID": NEWEST_SECRET,
                "FAKE_PUT_LOG": str(put_log),
            }
            for secret_id, token in (
                (NEWEST_SECRET + "-wrong", SYNTHETIC_TOKEN),
                (NEWEST_SECRET, "wrong-token"),
            ):
                with self.subTest(
                    secret_id=secret_id, token_is_correct=token == SYNTHETIC_TOKEN
                ):
                    payload = json.dumps(
                        {"token": token, "expires_at": "valid"}, separators=(",", ":")
                    )
                    result = subprocess.run(
                        [
                            str(fake_bin / "aws"),
                            "secretsmanager",
                            "put-secret-value",
                            "--secret-id",
                            secret_id,
                            "--secret-string",
                            payload,
                        ],
                        env=environment,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(put_log.exists())
                    self.assertNotIn(SYNTHETIC_TOKEN, result.stdout + result.stderr)

    def test_bad_secret_selection_never_writes_or_prints_token(self):
        for selected in ("null", "[]", "{}", '""', '"one"\n"two"', "{"):
            with self.subTest(selected=selected):
                result, puts = self.run_rotation("valid", selector_json=selected)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("No active secret found", result.stdout)
                self.assertEqual(puts, [])
                self.assertNotIn(SYNTHETIC_TOKEN, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
