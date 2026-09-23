"""Offline contracts for infrastructure-triggered CRM deployment during migration."""

import os
from pathlib import Path
import re
import subprocess
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[3]

# Stub only external commands. Execute the actual buildspec's shell control flow
# without credentials or AWS access, including parser and pipeline failures.
STUBS = r"""
python3() {
  if [ "$PARSER_EXIT" != 0 ]; then return "$PARSER_EXIT"; fi
  printf '%s\n' "$MIGRATION_STATUS"
}
aws() {
  printf 'AWS'; printf ' <%s>' "$@"; printf '\n'
  return "$PIPELINE_EXIT"
}
"""


class CrmUpWafMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = yaml.safe_load((ROOT / "aws/buildspecs/crm/up.yml").read_text())
        cls.commands = spec["phases"]["build"]["commands"]
        cls.trigger = next(
            command for command in cls.commands if "migration_in_progress=" in command
        )

    def execute(self, status="false", parser_exit=0, pipeline_exit=0, revision="abc123"):
        environment = {
            "PATH": os.defpath,
            "MIGRATION_STATUS": status,
            "PARSER_EXIT": str(parser_exit),
            "PIPELINE_EXIT": str(pipeline_exit),
            "CI_CD_CRM_PIPELINE_NAME": "crm-pipeline",
        }
        if revision is not None:
            environment["CODEBUILD_RESOLVED_SOURCE_VERSION"] = revision
        return subprocess.run(
            ["/bin/bash", "-c", STUBS + self.trigger],
            env=environment,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_stable_deployment_pins_infrastructure_source_revision(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "AWS <codepipeline> <start-pipeline-execution> <--name> <crm-pipeline> "
            "<--source-revisions> "
            "<actionName=Download-Source,revisionType=COMMIT_ID,revisionValue=abc123>\n",
        )

    def test_migration_defers_without_requiring_a_source_revision(self):
        result = self.execute(status="true", revision=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("AWS", result.stdout)
        self.assertIn("deployment is deferred", result.stdout)

    def test_parser_failure_is_fatal(self):
        result = self.execute(parser_exit=2)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot read WAF migration status", result.stdout)
        self.assertNotIn("AWS", result.stdout)

    def test_invalid_or_empty_migration_status_is_fatal(self):
        for status in ("", "None", "False", "unexpected"):
            with self.subTest(status=status):
                result = self.execute(status=status)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Invalid WAF migration status", result.stdout)
                self.assertNotIn("AWS", result.stdout)

    def test_missing_or_empty_source_revision_is_fatal_before_trigger(self):
        for revision in (None, ""):
            with self.subTest(revision=revision):
                result = self.execute(revision=revision)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Missing source revision", result.stderr)
                self.assertNotIn("AWS", result.stdout)

    def test_pipeline_failure_is_fatal(self):
        result = self.execute(pipeline_exit=9)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Error starting CodePipeline", result.stdout)

    def test_post_apply_helper_cannot_reattach_policy_during_migration(self):
        self.assertNotIn("distribution_deploy.py", "\n".join(self.commands))

    def test_origin_ownership_is_preserved_for_both_distributions(self):
        config = (ROOT / "terraform/app/modules/aws/cloudfront/main.tf").read_text()
        ignored = re.findall(r"ignore_changes\s*=\s*\[([^\]]*)\]", config)
        self.assertEqual([fields.strip() for fields in ignored], ["origin", "origin"])


if __name__ == "__main__":
    unittest.main()
