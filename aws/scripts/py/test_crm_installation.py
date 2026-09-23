"""The content pipeline must build its immutable CRM source artifact, not main."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "sh" / "crm_installation.sh"


class CrmInstallationTests(unittest.TestCase):
    def run_install(self, package=True, revision="a" * 40):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            if package:
                (source / "package.json").write_text('{"name":"crm"}')
                (source / ".env.example").write_text("EXAMPLE=true\n")
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; test -f .env.example',
                    "test",
                    str(SCRIPT),
                ],
                env={
                    "PATH": os.environ["PATH"],
                    "CODEBUILD_SRC_DIR": str(root),
                    "CODEBUILD_SRC_DIR_CrmSource": str(source),
                    "CRM_SOURCE_VERSION": revision,
                },
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result

    def test_immutable_artifact_and_dotfiles_are_copied_without_git(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_package_is_rejected(self):
        self.assertNotEqual(self.run_install(package=False).returncode, 0)

    def test_missing_source_revision_is_rejected(self):
        self.assertNotEqual(self.run_install(revision="").returncode, 0)


if __name__ == "__main__":
    unittest.main()
