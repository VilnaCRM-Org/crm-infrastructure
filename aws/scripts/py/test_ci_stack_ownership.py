"""Offline contracts for CRM stack ownership, quality gates, and deployment locking."""

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
        expected_stages = [
            (
                "batch-unit-mutation-lint",
                "Build",
                "AWS",
                "CodeBuild",
                "UnitMutationLintOutput",
                ["SourceOutput", "CrmSource"],
            ),
            (
                "deploy",
                "Build",
                "AWS",
                "CodeBuild",
                "DeployOutput",
                ["SourceOutput", "CrmSource"],
            ),
            (
                "healthcheck",
                "Build",
                "AWS",
                "CodeBuild",
                "HealthcheckOutput",
                ["SourceOutput", "CrmSource", "DeployOutput"],
            ),
            (
                "batch-lhci-leak",
                "Build",
                "AWS",
                "CodeBuild",
                "LHCILeakOutput",
                ["SourceOutput", "CrmSource"],
            ),
            (
                "batch-pw-load",
                "Build",
                "AWS",
                "CodeBuild",
                "PWLoadOutput",
                ["SourceOutput", "CrmSource"],
            ),
            (
                "release",
                "Build",
                "AWS",
                "CodeBuild",
                "ReleaseOutput",
                ["SourceOutput", "CrmSource", "DeployOutput"],
            ),
        ]

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
                r'\{\s*name\s*=\s*"([^"]+)",\s*'
                r'category\s*=\s*"([^"]+)",\s*'
                r'owner\s*=\s*"([^"]+)",\s*'
                r'provider\s*=\s*"([^"]+)",\s*'
                r"input_artifacts\s*=\s*\[([^\]]+)\],\s*"
                r'output_artifacts\s*=\s*"([^"]+)"\s*\}',
                stages,
            )
            actual_stages = [
                (
                    name,
                    category,
                    owner,
                    provider,
                    output,
                    re.findall(r'"([^"]+)"', inputs),
                )
                for name, category, owner, provider, inputs, output in actions
            ]
            with self.subTest(environment=environment):
                self.assertEqual(actual_stages, expected_stages)

    def test_infrastructure_and_content_are_queued_v2(self):
        for module in ("infrastructure", "crm"):
            config = (
                ROOT / f"terraform/app/modules/aws/codepipeline/{module}/main.tf"
            ).read_text()
            self.assertRegex(config, r'pipeline_type\s*=\s*"V2"')
            self.assertRegex(config, r'execution_mode\s*=\s*"QUEUED"')
            iterator = "action" if module == "crm" else "stage"
            self.assertIn(f"{iterator}.value.input_artifacts[0]", config)

    def test_crm_deploy_through_release_share_one_stage_lock(self):
        config = (
            ROOT / "terraform/app/modules/aws/codepipeline/crm/main.tf"
        ).read_text()
        # The two slices cover every configured action exactly once. Only core
        # tests may run in another stage while an execution owns shared staging.
        groups = re.findall(
            r'name\s*=\s*"(Stage-[^"]+)"\s*'
            r"actions\s*=\s*slice\(var.stages,\s*(\d+),\s*(1|length\(var.stages\))\)",
            config,
        )
        self.assertEqual(
            groups,
            [
                ("Stage-batch-unit-mutation-lint", "0", "1"),
                ("Stage-deployment", "1", "length(var.stages)"),
            ],
        )
        self.assertEqual(len(re.findall(r"\bstage\s*\{", config)), 1)  # Source only
        self.assertEqual(config.count('dynamic "stage"'), 1)
        self.assertRegex(
            config,
            r"content\s*\{\s*name\s*=\s*stage.value.name\s*"
            r'dynamic "action"\s*\{\s*for_each\s*=\s*stage.value.actions',
        )
        self.assertRegex(config, r"run_order\s*=\s*action.key\s*\+\s*1")
        self.assertRegex(config, r'execution_mode\s*=\s*"QUEUED"')

        # Validate each environment's actual inputs against the grouping, not
        # only the QUEUED flag (which cannot prevent overlap between stages).
        for environment in ("test", "prod"):
            variables = (
                ROOT
                / "terraform/app/stacks/ci-cd-infrastructure-crm/tfvars"
                / f"{environment}.tfvars"
            ).read_text()
            actions = re.search(
                r"ci_cd_crm_stage_input\s*=\s*\[(.*?)\n\]", variables, re.DOTALL
            ).group(1)
            names = re.findall(r'name\s*=\s*"([^"]+)"', actions)
            with self.subTest(environment=environment):
                self.assertEqual(names[:1], ["batch-unit-mutation-lint"])
                self.assertEqual(
                    list(enumerate(names[1:], start=1)),
                    [
                        (1, "deploy"),
                        (2, "healthcheck"),
                        (3, "batch-lhci-leak"),
                        (4, "batch-pw-load"),
                        (5, "release"),
                    ],
                )

    def test_crm_stage_grouping_rejects_missing_or_reordered_gates(self):
        variables = (
            ROOT / "terraform/app/modules/aws/codepipeline/crm/variables.tf"
        ).read_text()
        self.assertRegex(
            variables,
            r'condition\s*=\s*join\(",",\s*var.stages\[\*\].name\)\s*==\s*'
            r'"batch-unit-mutation-lint,deploy,healthcheck,batch-lhci-leak,batch-pw-load,release"',
        )

    def test_grouped_crm_actions_preserve_artifacts_batch_and_source_identity(self):
        config = (
            ROOT / "terraform/app/modules/aws/codepipeline/crm/main.tf"
        ).read_text()
        for field in ("category", "owner", "provider", "input_artifacts"):
            self.assertRegex(config, rf"{field}\s*=\s*action.value.{field}")
        self.assertRegex(
            config, r"output_artifacts\s*=\s*\[action.value.output_artifacts\]"
        )
        self.assertRegex(config, r'name\s*=\s*"Action-\$\{action.value.name\}"')
        for flag in ("CombineArtifacts", "BatchEnabled"):
            self.assertRegex(
                config,
                rf'{flag}\s*=\s*startswith\(action.value.name, "batch"\) \? true : false',
            )
        self.assertRegex(
            config,
            r'ProjectName\s*=\s*action.value.provider == "CodeBuild" \? '
            r'"\$\{var.project_name\}-\$\{action.value.name\}" : null',
        )
        self.assertRegex(
            config,
            r'PrimarySource\s*=\s*action.value.provider == "CodeBuild" && '
            r"length\(action.value.input_artifacts\) > 1 \? action.value.input_artifacts\[0\] : null",
        )
        self.assertRegex(
            config,
            r'EnvironmentVariables\s*=\s*action.value.provider == "CodeBuild" \? '
            r'jsonencode\(\[\s*\{\s*name\s*=\s*"CRM_SOURCE_VERSION"\s*'
            r'value\s*=\s*"#\{CrmSourceVariables.CommitId\}"\s*type\s*=\s*"PLAINTEXT"',
        )


if __name__ == "__main__":
    unittest.main()
