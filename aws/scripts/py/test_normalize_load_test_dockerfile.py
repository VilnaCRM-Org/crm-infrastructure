"""CRM load-test Dockerfile discovery and normalization contract."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1] / "sh" / "normalize_load_test_dockerfile.sh"
)


class NormalizeLoadTestDockerfileTests(unittest.TestCase):
    def run_normalizer(self, filename):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dockerfile = root / "crm" / "tests" / "load" / filename
            dockerfile.parent.mkdir(parents=True)
            dockerfile.write_text(
                "FROM golang:1.25.8-alpine3.22 AS builder\n" "FROM alpine:3.22\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["bash", str(SCRIPT)],
                env={**os.environ, "CODEBUILD_SRC_DIR": str(root)},
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result, dockerfile.read_text(encoding="utf-8")

    def assert_normalized(self, filename):
        result, contents = self.run_normalizer(filename)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "public.ecr.aws/docker/library/golang:1.25.8-alpine3.22 AS builder",
            contents,
        )
        self.assertIn("public.ecr.aws/docker/library/alpine:3.22", contents)

    def test_discovers_and_normalizes_current_lowercase_compose_path(self):
        self.assert_normalized("dockerfile")

    def test_keeps_legacy_uppercase_dockerfile_path_supported(self):
        self.assert_normalized("Dockerfile")


if __name__ == "__main__":
    unittest.main()
