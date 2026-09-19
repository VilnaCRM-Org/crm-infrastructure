"""Regression tests for explicit CRM CodeBuild shell selection."""

import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CRM_BUILDSPECS = REPOSITORY_ROOT / "aws" / "buildspecs" / "crm"
BUILDSPEC_PATHS = [
    *(CRM_BUILDSPECS / "batches").glob("*.yml"),
    CRM_BUILDSPECS / "deploy.yml",
    CRM_BUILDSPECS / "healthcheck.yml",
    CRM_BUILDSPECS / "release.yml",
]


class BuildspecShellTests(unittest.TestCase):
    def test_crm_content_buildspecs_explicitly_select_bash(self):
        self.assertEqual(len(BUILDSPEC_PATHS), 13)
        for buildspec_path in BUILDSPEC_PATHS:
            with self.subTest(buildspec=buildspec_path.name):
                with buildspec_path.open(encoding="utf-8") as buildspec_file:
                    buildspec = yaml.safe_load(buildspec_file)
                self.assertEqual(buildspec["env"]["shell"], "bash")


if __name__ == "__main__":
    unittest.main()
