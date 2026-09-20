"""Offline Alpine bootstrap contracts; execute only temporary stub helpers."""

import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CRM_BUILDSPECS = REPOSITORY_ROOT / "aws" / "buildspecs" / "crm"
BATCH_TARGETS = {
    "unit": ("batch_unit_mutation_integration_lint.sh", "test-unit"),
    "mutation": ("batch_unit_mutation_integration_lint.sh", "test-mutation"),
    "integration": ("batch_unit_mutation_integration_lint.sh", "test-integration"),
    "lint": ("batch_unit_mutation_integration_lint.sh", "test-lint"),
    "lighthouse_desktop": ("batch_lhci_leak.sh", "test-lighthouse-desktop"),
    "lighthouse_mobile": ("batch_lhci_leak.sh", "test-lighthouse-mobile"),
    "memory_leak": ("batch_lhci_leak.sh", "test-memory-leak"),
    "playwright_e2e": ("batch_pw_load.sh", "test-playwright-e2e"),
    "playwright_visual": ("batch_pw_load.sh", "test-playwright-visual"),
    "load_test": ("batch_pw_load.sh", "test-load"),
}

CREATE_ENV = r"""
[[ -n ${BASH_VERSION:-} ]]
[[ $PWD == "$CODEBUILD_SRC_DIR/crm" ]]
values=(synthetic exported)
export SYNTHETIC_EXPORTED="${values[*]}"
printf 'env:%s\n' "$SYNTHETIC_PHASE" >> "$SYNTHETIC_TRACE"
"""

BATCH_HELPER = r"""
[[ -n ${BASH_VERSION:-} ]]
[[ $PWD == "$CODEBUILD_SRC_DIR/crm" ]]
[[ $1 == "$SYNTHETIC_TARGET" || $1 == "${SYNTHETIC_SECOND_TARGET:-}" ]]
bash -c '[[ $SYNTHETIC_EXPORTED == "synthetic exported" ]]'
printf 'helper:%s\n' "$1" >> "$SYNTHETIC_TRACE"
export BUILD_ONLY=must-not-be-needed-by-finally
if [[ ${SYNTHETIC_FAIL_TARGET:-} == "$1" ]]; then
  exit 37
fi
# A failing command must stop the Bash heredoc before the success marker.
(exit "$SYNTHETIC_BUILD_EXIT")
printf 'build-complete\n' >> "$SYNTHETIC_TRACE"
"""

RUN_REPORTS = r"""
[[ -n ${BASH_VERSION:-} ]]
[[ $PWD == "$CODEBUILD_SRC_DIR/crm" ]]
[[ -z ${BUILD_ONLY:-} ]]
bash -c '[[ $SYNTHETIC_EXPORTED == "synthetic exported" ]]'
printf 'reports\n' >> "$SYNTHETIC_TRACE"
"""


def load_buildspec(name, batch=True):
    directory = CRM_BUILDSPECS / "batches" if batch else CRM_BUILDSPECS
    return yaml.safe_load((directory / f"{name}.yml").read_text(encoding="utf-8"))


class BuildspecShellTests(unittest.TestCase):
    def test_lighthouse_report_selection_survives_independent_finally_shell(self):
        for mode in ("desktop", "mobile"):
            with self.subTest(mode=mode):
                variables = load_buildspec(f"lighthouse_{mode}")["env"]["variables"]
                self.assertEqual(variables[f"LHCI_{mode.upper()}_RUN"], "1")
                self.assertEqual(
                    [
                        name
                        for name in variables
                        if name.startswith("LHCI_") and name.endswith("_RUN")
                    ],
                    [f"LHCI_{mode.upper()}_RUN"],
                )

    def test_aws_mutation_is_deferred_but_other_quality_children_remain_required(self):
        batch = load_buildspec("batch_unit_mutation_integration_lint", batch=False)[
            "batch"
        ]
        self.assertFalse(batch["fast-fail"])
        self.assertEqual(len(batch["build-list"]), 3)
        children = {child["identifier"]: child for child in batch["build-list"]}
        self.assertEqual(set(children), {"unit", "integration", "lint"})
        for name, child in children.items():
            with self.subTest(child=name):
                self.assertFalse(child["ignore-failure"])
                self.assertEqual(
                    child["buildspec"], f"./aws/buildspecs/crm/batches/{name}.yml"
                )
                self.assertEqual(
                    child.get("env", {}),
                    {
                        "unit": {"compute-type": "BUILD_GENERAL1_MEDIUM"},
                    }.get(name, {}),
                )

    def assert_bash_heredoc(self, command):
        self.assertTrue(command.startswith("bash -e <<'BASH'\n"), command)
        self.assertEqual(command.rstrip().splitlines()[-1], "BASH")

    def test_ten_alpine_batches_start_with_sh(self):
        self.assertEqual(
            {path.stem for path in (CRM_BUILDSPECS / "batches").glob("*.yml")},
            set(BATCH_TARGETS),
        )
        for name in BATCH_TARGETS:
            with self.subTest(buildspec=name):
                self.assertEqual(load_buildspec(name)["env"]["shell"], "/bin/sh")

    def test_managed_image_content_stages_keep_bash(self):
        for name in ("deploy", "healthcheck", "release"):
            with self.subTest(buildspec=name):
                self.assertEqual(
                    load_buildspec(name, batch=False)["env"]["shell"], "bash"
                )

    def test_install_bootstraps_bash_before_sourcing_helpers(self):
        for name in BATCH_TARGETS:
            with self.subTest(buildspec=name):
                commands = load_buildspec(name)["phases"]["install"]["commands"]
                self.assertEqual(len(commands), 2)
                self.assertEqual(
                    shlex.split(commands[0]),
                    [
                        "/bin/sh",
                        "${CODEBUILD_SRC_DIR}/${SCRIPT_DIR}/sh/install_packages.sh",
                    ],
                )
                self.assert_bash_heredoc(commands[1])
                helpers = ["crm_installation.sh", "setup_docker.sh"]
                if name == "load_test":
                    helpers = [
                        "crm_installation.sh",
                        "normalize_load_test_dockerfile.sh",
                        "setup_docker.sh",
                        "k6_installation.sh",
                    ]
                positions = [commands[1].index(helper) for helper in helpers]
                self.assertEqual(positions, sorted(positions))
                for helper in helpers:
                    self.assertEqual(commands[1].count(helper), 1)
                self.assertNotIn("install_packages.sh", commands[1])

    def run_stubbed_phases(self, name, build_exit=None, fail_target=None):
        buildspec = load_buildspec(name)
        phase = buildspec["phases"]["build"]
        self.assertEqual(len(phase["commands"]), 1)
        self.assert_bash_heredoc(phase["commands"][0])
        self.assert_bash_heredoc(phase["finally"][0])
        helper, target = BATCH_TARGETS[name]
        targets = [target]
        if name == "load_test":
            targets.append("test-load-signup")
        self.assertIn(helper, phase["commands"][0])
        with tempfile.TemporaryDirectory(prefix="crm-shell-test-") as temporary:
            root = Path(temporary)
            scripts = root / "aws/scripts/sh"
            helpers = root / "crm/scripts/ci"
            scripts.mkdir(parents=True)
            helpers.mkdir(parents=True)
            (scripts / "create_env.sh").write_text(CREATE_ENV, encoding="utf-8")
            (scripts / "run_reports.sh").write_text(RUN_REPORTS, encoding="utf-8")
            (helpers / helper).write_text(BATCH_HELPER, encoding="utf-8")
            trace = root / "trace.txt"
            # No host credentials, pre-exported test values, or shell startup files.
            environment = {
                "PATH": os.defpath,
                "CODEBUILD_SRC_DIR": str(root),
                "SCRIPT_DIR": "aws/scripts",
                "SYNTHETIC_TRACE": str(trace),
                "SYNTHETIC_TARGET": target,
                "SYNTHETIC_SECOND_TARGET": targets[1] if len(targets) > 1 else "",
                "SYNTHETIC_FAIL_TARGET": fail_target or "",
                "SYNTHETIC_BUILD_EXIT": str(build_exit or 0),
            }

            def execute(command, phase_name):
                return subprocess.run(
                    ["/bin/sh", "-c", command],
                    cwd=root,
                    env={**environment, "SYNTHETIC_PHASE": phase_name},
                    text=True,
                    capture_output=True,
                    timeout=10,
                )

            expected = []
            if build_exit is not None:
                result = execute(phase["commands"][0], "build")
                expected_build_status = 37 if fail_target else build_exit
                self.assertEqual(
                    result.returncode,
                    expected_build_status,
                    result.stdout + result.stderr,
                )
                expected = ["env:build"]
                for current_target in targets:
                    expected.append(f"helper:{current_target}")
                    if fail_target == current_target or build_exit != 0:
                        break
                    expected.append("build-complete")
                self.assertEqual(trace.read_text().splitlines(), expected)

            # CodeBuild invokes finally separately even when build fails. Each
            # command here starts a fresh shell, cwd, and environment deliberately.
            for command in phase["finally"]:
                result = execute(command, "finally")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                trace.read_text().splitlines(), expected + ["env:finally", "reports"]
            )
            for artifact in buildspec["artifacts"]["files"]:
                self.assertTrue((root / artifact).is_file(), artifact)

    def test_build_and_finally_run_bash_helpers_with_exported_environment(self):
        for name in BATCH_TARGETS:
            with self.subTest(buildspec=name):
                self.run_stubbed_phases(name, build_exit=0)

    def test_build_failure_retains_exit_code_and_finally_runs_independently(self):
        for name in BATCH_TARGETS:
            with self.subTest(buildspec=name):
                self.run_stubbed_phases(name, build_exit=37)

    def test_finally_does_not_require_build_to_have_run(self):
        for name in BATCH_TARGETS:
            with self.subTest(buildspec=name):
                self.run_stubbed_phases(name)

    def test_load_batch_runs_signup_after_homepage_and_propagates_signup_failure(self):
        self.run_stubbed_phases("load_test", build_exit=0)
        self.run_stubbed_phases(
            "load_test", build_exit=0, fail_target="test-load-signup"
        )


if __name__ == "__main__":
    unittest.main()
