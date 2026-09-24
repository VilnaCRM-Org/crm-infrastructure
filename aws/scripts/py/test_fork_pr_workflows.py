"""Offline security contracts for fork lint, cost checks, and Terraform docs."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
INTERNAL = "github.event.pull_request.head.repo.full_name == github.repository"
TRUSTED_INTERNAL = (
    "github.event.pull_request.head.repo.full_name == github.repository && "
    "github.event.pull_request.user.login != 'dependabot[bot]'"
)
FORK = "github.event.pull_request.head.repo.full_name != github.repository"
DEPENDABOT = (
    "github.event.pull_request.head.repo.full_name == github.repository && "
    "github.event.pull_request.user.login == 'dependabot[bot]'"
)


def workflow(name):
    path = ROOT / ".github/workflows" / name
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


class ForkWorkflowPermissionsTests(unittest.TestCase):
    def test_workflows_only_use_unprivileged_pull_request_events(self):
        for name in ("super-linter.yml", "infracost.yml", "tf_docs.yml"):
            with self.subTest(workflow=name):
                data = workflow(name)
                self.assertEqual(set(data["on"]), {"pull_request"})
                self.assertEqual(data["permissions"], {"contents": "read"})

    def test_fork_lint_disables_tokens_writes_fixes_and_status_reports(self):
        job = workflow("super-linter.yml")["jobs"]["lint"]
        self.assertNotIn("permissions", job)
        token, checkout, lint, commit = job["steps"]
        self.assertEqual(token["if"], TRUSTED_INTERNAL)
        self.assertIn("secrets.VILNACRM_APP_PRIVATE_KEY", str(token))
        self.assertEqual(
            checkout["with"]["persist-credentials"], "${{ " + TRUSTED_INTERNAL + " }}"
        )
        for value in (
            checkout["with"]["token"],
            lint["env"]["GITHUB_TOKEN"],
        ):
            self.assertEqual(
                value, "${{ steps.generate_token.outputs.token || github.token }}"
            )
        flags = [key for key in lint["env"] if key.startswith("FIX_")]
        self.assertEqual(len(flags), 5)
        for flag in flags + ["MULTI_STATUS"]:
            self.assertEqual(lint["env"][flag], "${{ " + TRUSTED_INTERNAL + " }}")
        self.assertTrue(commit["if"].startswith(TRUSTED_INTERNAL + " &&"))
        self.assertEqual(commit["uses"], "stefanzweifel/git-auto-commit-action@v5")

    def test_infracost_secrets_and_comment_writes_are_internal_only(self):
        data = workflow("infracost.yml")
        self.assertNotIn("secrets.", str(data.get("env", {})))
        jobs = data["jobs"]
        fork = jobs["fork-cost-policy"]
        self.assertEqual(fork["if"], FORK)
        self.assertNotIn("permissions", fork)
        self.assertNotIn("secrets.", str(fork))
        self.assertNotIn("infracost/actions", str(fork))
        checkout = fork["steps"][0]["with"]
        self.assertEqual(checkout["persist-credentials"], "false")
        self.assertEqual(checkout["fetch-depth"], "0")
        self.assertEqual(
            checkout["ref"],
            "refs/pull/${{ github.event.pull_request.number }}/head",
        )
        dependabot = jobs["dependabot-cost-policy"]
        self.assertEqual(dependabot["if"], DEPENDABOT)
        self.assertNotIn("permissions", dependabot)
        self.assertNotIn("secrets.", str(dependabot))
        self.assertNotIn("infracost/actions", str(dependabot))
        self.assertEqual(dependabot["steps"][0]["with"], checkout)
        internal = jobs["internal-infracost"]
        self.assertEqual(internal["if"], TRUSTED_INTERNAL)
        self.assertEqual(internal["permissions"]["pull-requests"], "write")
        self.assertIn("secrets.INFRACOST_API_KEY", str(internal))
        commands = str(internal["steps"])
        for command in ("infracost breakdown", "infracost diff", "infracost comment"):
            self.assertIn(command, commands)

    def test_fork_docs_uses_immutable_head_without_credentials_or_push(self):
        jobs = workflow("tf_docs.yml")["jobs"]
        fork = jobs["fork-terraform-docs"]
        self.assertEqual(fork["if"], FORK)
        self.assertNotIn("permissions", fork)
        self.assertNotIn("secrets.", str(fork))
        checkout, render = fork["steps"]
        self.assertEqual(
            checkout["with"],
            {
                "ref": "${{ github.event.pull_request.head.sha }}",
                "persist-credentials": "false",
            },
        )
        self.assertEqual(render["with"]["git-push"], "false")
        self.assertEqual(render["with"]["fail-on-diff"], "true")
        self.assertEqual(render["with"]["output-file"], "README.md")
        internal = jobs["internal-terraform-docs"]
        self.assertEqual(internal["if"], INTERNAL)
        self.assertEqual(internal["permissions"], {"contents": "write"})
        self.assertEqual(internal["steps"][1]["with"]["git-push"], "true")

    def test_original_required_checks_propagate_failures_and_skips(self):
        for name, gate in (
            ("infracost.yml", "infracost"),
            ("tf_docs.yml", "terraform-docs"),
        ):
            job = workflow(name)["jobs"][gate]
            self.assertEqual(job["if"], "always()")
            self.assertNotIn("permissions", job)
            step = job["steps"][0]
            if name == "infracost.yml":
                self.assertEqual(
                    job["needs"],
                    [
                        "fork-cost-policy",
                        "dependabot-cost-policy",
                        "internal-infracost",
                    ],
                )
                self.assertEqual(
                    step["env"]["IS_INTERNAL"], "${{ " + TRUSTED_INTERNAL + " }}"
                )
                self.assertEqual(
                    step["env"]["IS_DEPENDABOT"], "${{ " + DEPENDABOT + " }}"
                )
                routes = (
                    ("internal", "true", "false", "INTERNAL_RESULT"),
                    ("dependabot", "false", "true", "DEPENDABOT_RESULT"),
                    ("fork", "false", "false", "FORK_RESULT"),
                )
            else:
                self.assertEqual(len(job["needs"]), 2)
                self.assertEqual(step["env"]["IS_INTERNAL"], "${{ " + INTERNAL + " }}")
                routes = (
                    ("internal", "true", "false", "INTERNAL_RESULT"),
                    ("fork", "false", "false", "FORK_RESULT"),
                )
            for route, is_internal, is_dependabot, selected_result in routes:
                for status in ("success", "failure", "cancelled", "skipped"):
                    with self.subTest(workflow=name, route=route, status=status):
                        env = {
                            **os.environ,
                            "IS_INTERNAL": is_internal,
                            "IS_DEPENDABOT": is_dependabot,
                            "FORK_RESULT": "skipped",
                            "DEPENDABOT_RESULT": "skipped",
                            "INTERNAL_RESULT": "skipped",
                        }
                        env[selected_result] = status
                        result = subprocess.run(
                            ["bash", "-e", "-c", step["run"]],
                            env=env,
                            capture_output=True,
                        )
                        self.assertEqual(result.returncode == 0, status == "success")


class ForkCostPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.email", "offline@example.invalid")
        self.git("config", "user.name", "Offline test")
        self.write("README.md")
        self.write("terraform/main.tf")
        self.base = self.commit()
        self.script = workflow("infracost.yml")["jobs"]["fork-cost-policy"]["steps"][1][
            "run"
        ]

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args], cwd=self.repo, text=True, stderr=subprocess.PIPE
        ).strip()

    def write(self, path, content="test\n"):
        file = self.repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "-qm", "Offline fixture")
        return self.git("rev-parse", "HEAD")

    def run_policy(self, base=None, head=None):
        return subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", self.script],
            cwd=self.repo,
            env={
                **os.environ,
                "BASE_SHA": base or self.base,
                "HEAD_SHA": head or self.git("rev-parse", "HEAD"),
            },
            capture_output=True,
            text=True,
        )

    def test_workflows_scripts_and_docs_need_no_key(self):
        for path in (
            ".github/workflows/infracost.yml",
            ".github/workflows/super-linter.yml",
            "aws/scripts/py/rotate.py",
            "docs/readme.md",
        ):
            self.write(path)
        self.commit()
        result = self.run_policy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no Infracost key required", result.stdout)

    def test_cost_inputs_fail_closed(self):
        for path in (
            "terraform/main.tf",
            "terraform/config/project.rb",
            "external/module.tf",
            "external/module.tf.json",
            "external/test.tfvars",
            "external/test.tfvars.json",
            "external/.terraform.lock.hcl",
            "external/saved.tfplan",
            "external/plan.json",
            "infracost.yml",
            "config/infracost-usage.yaml",
            "config/infracost.json",
            "terraform/space and\nnewline.txt",
        ):
            with self.subTest(path=path):
                previous = self.git("rev-parse", "HEAD")
                self.write(path, "changed\n")
                self.commit()
                result = self.run_policy(base=previous)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("trusted internal PR", result.stderr)

    def test_deleting_or_renaming_terraform_input_fails(self):
        self.git("mv", "terraform/main.tf", "renamed.txt")
        self.commit()
        result = self.run_policy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("terraform/main.tf", result.stdout)
        (self.repo / "renamed.txt").unlink()
        self.commit()
        result = self.run_policy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("terraform/main.tf", result.stdout)

    def test_complete_diff_is_not_limited_to_first_300_files(self):
        for index in range(310):
            self.write(f"docs/{index}.md")
        self.write("terraform/last.tf")
        self.commit()
        result = self.run_policy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("terraform/last.tf", result.stdout)

    def test_missing_commit_and_changed_head_fail_closed(self):
        for kwargs in ({"base": "0" * 40}, {"head": "0" * 40}):
            with self.subTest(kwargs=kwargs):
                self.assertNotEqual(self.run_policy(**kwargs).returncode, 0)

    def test_base_only_terraform_changes_do_not_block_workflow_pr(self):
        self.write("terraform/base-only.tf")
        advanced_base = self.commit()
        self.git("checkout", "--detach", self.base)
        self.write(".github/workflows/example.yml")
        self.commit()
        result = self.run_policy(base=advanced_base)
        self.assertEqual(result.returncode, 0, result.stderr)


class DependabotCostPolicyTests(ForkCostPolicyTests):
    """The dedicated no-secret Dependabot path obeys the same fail-closed diff policy."""

    def setUp(self):
        super().setUp()
        self.script = workflow("infracost.yml")["jobs"]["dependabot-cost-policy"][
            "steps"
        ][1]["run"]


if __name__ == "__main__":
    unittest.main()
