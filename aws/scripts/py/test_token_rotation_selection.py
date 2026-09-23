"""Read-only rotation contracts using synthetic metadata; never invokes AWS.

JMESPath is provided by boto3, already installed by deployment-tests.yml.
"""

from itertools import permutations
from pathlib import Path
import re
import unittest

import jmespath


ROOT = Path(__file__).resolve().parents[3]


def selection_query(script_name):
    script = (ROOT / "aws/scripts/sh" / script_name).read_text()
    query = re.search(
        r'SECRET_ID=\$\((?:aws|_github_token_aws) secretsmanager list-secrets\b.*?--query "([^"]+)"',
        script,
        re.DOTALL,
    )
    if query is None:
        raise AssertionError(f"Missing selection query in {script_name}")
    return query.group(1)


class TokenRotationSelectionTests(unittest.TestCase):
    def setUp(self):
        self.queries = [
            selection_query(name)
            for name in ("retrieve_token.sh", "rotate_github_token.sh")
        ]

    def test_rotation_and_loader_use_identical_selection(self):
        self.assertEqual(self.queries[0], self.queries[1])

    def test_newest_active_match_is_selected_regardless_of_list_order(self):
        secrets = [
            {"Name": "crm-github-token-old", "CreatedDate": 100},
            {
                "Name": "crm-github-token-current",
                "CreatedDate": 200,
                "DeletedDate": None,
            },
            {
                "Name": "crm-github-token-deleted",
                "CreatedDate": 300,
                "DeletedDate": 400,
            },
            {"Name": "other-github-token-unrelated", "CreatedDate": 500},
        ]
        for records in permutations(secrets):
            for query in self.queries:
                self.assertEqual(
                    jmespath.search(query, {"SecretList": list(records)}),
                    "crm-github-token-current",
                )

    def test_no_active_match_returns_null(self):
        for records in (
            [],
            [
                {
                    "Name": "crm-github-token-deleted",
                    "CreatedDate": 100,
                    "DeletedDate": 200,
                },
                {"Name": "unrelated", "CreatedDate": 300},
            ],
        ):
            for query in self.queries:
                self.assertIsNone(jmespath.search(query, {"SecretList": records}))

    def test_rotation_concurrency_is_environment_specific(self):
        for environment in ("test", "prod"):
            workflow = (
                ROOT / ".github/workflows" / f"github-token-rotation-{environment}.yml"
            ).read_text()
            groups = re.findall(r"^\s+group:\s*(\S+)\s*$", workflow, re.MULTILINE)
            self.assertEqual(groups, [f"github-token-rotation-{environment}"])


if __name__ == "__main__":
    unittest.main()
