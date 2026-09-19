"""Offline guard against CRM touching website-owned Terraform state."""

from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[3]
OWNED_STACKS = {"ci-cd-infrastructure-crm", "crm-iam"}
SHARED_STACK = re.compile(r"\b(?:ci-cd-iam|iam-groups)\b")
ALL_STACKS = re.compile(r"terraspace(?:-all-|\s+all\b)")


class CrmStackOwnershipTests(unittest.TestCase):
    def assert_scoped(self, commands):
        self.assertNotRegex(commands, SHARED_STACK)
        self.assertNotRegex(commands, ALL_STACKS)

    def test_pipeline_make_targets_only_reach_owned_stacks(self):
        for operation in ("init", "validate", "plan", "up-plan"):
            with self.subTest(operation=operation):
                # Dry-run recursive make only; never execute Terraspace or AWS.
                result = subprocess.run(
                    [
                        "make",
                        "--dry-run",
                        "--no-print-directory",
                        f"terraspace-ci-cd-infra-{operation}",
                        "env=test",
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=True,
                )
                self.assert_scoped(result.stdout)
                selections = re.findall(r"for stack in ([^;]+);", result.stdout)
                self.assertTrue(selections, result.stdout)
                for selection in selections:
                    self.assertEqual(set(selection.split()), OWNED_STACKS)

    def test_validation_task_uses_scoped_targets(self):
        task = (ROOT / "task/terraform_tests_ci_cd_infrastructure_crm.yml").read_text()
        self.assert_scoped(task)
        commands = re.findall(r"^\s+- (make terraspace[^\n]+)", task, re.MULTILINE)
        self.assertEqual(
            commands,
            [
                "make terraspace-ci-cd-infra-init",
                "make terraspace-ci-cd-infra-validate",
            ],
        )

    def test_pipeline_entrypoints_do_not_select_all_or_shared_stacks(self):
        for directory in ("ci-cd-infrastructure-crm", "crm"):
            for path in (ROOT / "aws/buildspecs" / directory).glob("*.yml"):
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assert_scoped(path.read_text())
        for name, target in (("plan", "plan"), ("up", "up-plan")):
            spec = (
                ROOT / f"aws/buildspecs/ci-cd-infrastructure-crm/{name}.yml"
            ).read_text()
            self.assertIn("make terraspace-ci-cd-infra-init", spec)
            self.assertIn(f"make terraspace-ci-cd-infra-{target}", spec)

    def test_test_and_production_content_stage_artifacts(self):
        for environment in ("test", "prod"):
            config = (
                ROOT
                / "terraform/app/stacks/ci-cd-infrastructure-crm/tfvars"
                / f"{environment}.tfvars"
            ).read_text()
            stages = re.search(
                r"ci_cd_crm_stage_input\s*=\s*\[(.*?)\n\]", config, re.DOTALL
            ).group(1)
            actions = re.findall(
                r'name\s*=\s*"([^"]+)"[^\n]*?' r"input_artifacts\s*=\s*\[([^\]]+)\]",
                stages,
            )
            names = {name for name, _ in actions}
            self.assertTrue({"deploy", "healthcheck", "release"} <= names)
            if environment == "prod":
                self.assertTrue(
                    {"batch-unit-mutation-lint", "batch-lhci-leak", "batch-pw-load"}
                    <= names
                )
            for name, inputs in actions:
                with self.subTest(environment=environment, stage=name):
                    expected = ["SourceOutput", "CrmSource"]
                    if name in ("healthcheck", "release"):
                        expected.append("DeployOutput")
                    self.assertEqual(re.findall(r'"([^"]+)"', inputs), expected)

    def test_infrastructure_and_content_are_queued_v2(self):
        for module in ("infrastructure", "crm"):
            config = (
                ROOT / f"terraform/app/modules/aws/codepipeline/{module}/main.tf"
            ).read_text()
            self.assertRegex(config, r'pipeline_type\s*=\s*"V2"')
            self.assertRegex(config, r'execution_mode\s*=\s*"QUEUED"')
            self.assertIn("stage.value.input_artifacts[0]", config)


if __name__ == "__main__":
    unittest.main()
