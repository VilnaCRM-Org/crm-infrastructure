"""Offline contracts for trusted rotation and the parent Terraform freshness gate."""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[3]


class TokenFreshnessContractTests(unittest.TestCase):
    def test_rotation_is_main_only_with_trusted_checkout_and_existing_authority(self):
        schedules = {
            "test": [{"cron": "11 * * * *"}, {"cron": "41 * * * *"}],
            "prod": [{"cron": "26 * * * *"}, {"cron": "56 * * * *"}],
        }
        for environment in ("test", "prod"):
            with self.subTest(environment=environment):
                workflow = yaml.load(
                    (
                        ROOT
                        / ".github/workflows"
                        / f"github-token-rotation-{environment}.yml"
                    ).read_text(),
                    Loader=yaml.BaseLoader,
                )
                triggers = workflow["on"]
                self.assertEqual(triggers["push"], {"branches": ["main"]})
                self.assertEqual(
                    set(triggers),
                    {"push", "schedule", "workflow_dispatch", "repository_dispatch"},
                )
                self.assertEqual(triggers["schedule"], schedules[environment])
                self.assertEqual(
                    triggers["repository_dispatch"],
                    {"types": [f"rotate_token_{environment}"]},
                )
                self.assertEqual(set(workflow["jobs"]), {"rotate-github-token"})
                job = workflow["jobs"]["rotate-github-token"]
                self.assertEqual(job["if"], "github.ref == 'refs/heads/main'")
                self.assertEqual(
                    job["permissions"], {"id-token": "write", "contents": "read"}
                )
                self.assertEqual(
                    job["concurrency"],
                    {
                        "group": f"github-token-rotation-{environment}",
                        "cancel-in-progress": "false",
                    },
                )
                checkouts = [
                    step
                    for step in job["steps"]
                    if step.get("uses", "").startswith("actions/checkout@")
                ]
                self.assertEqual(len(checkouts), 1)
                self.assertEqual(
                    checkouts[0]["with"],
                    {"ref": "refs/heads/main", "persist-credentials": "false"},
                )
                credentials = [
                    step
                    for step in job["steps"]
                    if step.get("uses", "").startswith(
                        "aws-actions/configure-aws-credentials@"
                    )
                ]
                self.assertEqual(len(credentials), 1)
                self.assertEqual(
                    credentials[0]["with"]["role-to-assume"],
                    "arn:aws:iam::${{vars."
                    + environment.upper()
                    + "_AWS_ACCOUNT_ID}}:role/github-actions-crm-role",
                )

    def test_parent_plan_and_apply_require_freshness_before_terraform(self):
        for stage, target in (("plan", "plan"), ("up", "up-plan")):
            with self.subTest(stage=stage):
                spec = yaml.safe_load(
                    (
                        ROOT
                        / "aws/buildspecs/ci-cd-infrastructure-crm"
                        / f"{stage}.yml"
                    ).read_text()
                )
                variables = spec["env"]["variables"]
                self.assertEqual(variables["GITHUB_TOKEN_WAIT_SECONDS"], "300")
                self.assertEqual(variables["GITHUB_TOKEN_MIN_TTL_SECONDS"], "900")
                self.assertEqual(variables["GITHUB_TOKEN_POLL_SECONDS"], "15")
                commands = spec["phases"]["build"]["commands"]
                loader = ". ${CODEBUILD_SRC_DIR}/${SCRIPT_DIR}/sh/retrieve_token.sh"
                self.assertEqual(commands.count(loader), 1)
                self.assertLess(
                    commands.index(loader),
                    commands.index(f"make terraspace-ci-cd-infra-{target}"),
                )


if __name__ == "__main__":
    unittest.main()
