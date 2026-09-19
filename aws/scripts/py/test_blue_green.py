"""Mocked regression coverage for CRM blue/green deployment scripts."""

import json
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cache_invalidation
import continuous_deployment_switch as policy
import deploy_content
import distribution_deploy
import origin_change


BUCKET = "app.vilnacrm.example"


def distribution(identifier, bucket, staging=False):
    replication_bucket = f"{bucket}-replication"
    return {
        "Id": identifier,
        "DomainName": f"{identifier}.cloudfront.net",
        "Staging": staging,
        "Enabled": True,
        "Aliases": {"Items": [] if staging else [bucket]},
        "Origins": {
            "Items": [
                {"Id": "origin", "DomainName": f"{bucket}.s3.eu-central-1.amazonaws.com"},
                {"Id": "replication", "DomainName": f"{replication_bucket}.s3.eu-west-1.amazonaws.com"},
            ]
        },
    }


class BlueGreenTests(unittest.TestCase):
    def test_origin_pair_recognizes_both_exact_regional_bucket_pairs(self):
        for base, role in ((BUCKET, "primary"), (f"staging.{BUCKET}", "staging")):
            pair = distribution("pair", base)["Origins"]["Items"]
            self.assertEqual(deploy_content.origin_pair_role(pair, BUCKET), role)
        incomplete = distribution("pair", BUCKET)["Origins"]["Items"][:1]
        mixed = distribution("pair", BUCKET)["Origins"]["Items"] + distribution(
            "other", f"staging.{BUCKET}", True
        )["Origins"]["Items"][:1]
        self.assertIsNone(deploy_content.origin_pair_role(incomplete, BUCKET))
        self.assertIsNone(deploy_content.origin_pair_role(mixed, BUCKET))
        wrong_region = distribution("wrong-region", BUCKET)["Origins"]["Items"]
        wrong_region[1]["DomainName"] = f"{BUCKET}-replication.s3.eu-central-1.amazonaws.com"
        self.assertIsNone(deploy_content.origin_pair_role(wrong_region, BUCKET))

    def test_staging_disabled_defaults_to_direct_primary_upload(self):
        with patch.dict(os.environ, {"ENABLE_CLOUDFRONT_STAGING": "false"}, clear=False), patch.object(
            deploy_content, "find_project_distributions", side_effect=AssertionError("AWS lookup should be skipped")
        ):
            self.assertEqual(deploy_content.determine_deployment_target(BUCKET), BUCKET)

    def test_staging_disabled_policy_switch_is_noop(self):
        with patch.object(policy, "ENABLE_CLOUDFRONT_STAGING", False), patch.object(
            policy.subprocess, "check_output", side_effect=AssertionError("AWS call should be skipped")
        ):
            policy.main()

    def test_distribution_match_is_exact_and_rejects_ambiguous_roles(self):
        items = [
            distribution("unrelated", "app.vilnacrm-other.example"),
            distribution("primary", BUCKET),
            distribution("staging", f"staging.{BUCKET}", True),
        ]
        with patch.object(
            deploy_content, "fetch_distributions", return_value={"DistributionList": {"Items": items}}
        ):
            result = deploy_content.find_project_distributions(BUCKET)
        self.assertEqual(result["production"]["Id"], "primary")
        self.assertEqual(result["staging"]["Id"], "staging")

        items.append(distribution("second-primary", BUCKET))
        with patch.object(
            deploy_content, "fetch_distributions", return_value={"DistributionList": {"Items": items}}
        ), self.assertRaises(ValueError):
            deploy_content.find_project_distributions(BUCKET)

    def test_project_lookup_keeps_staging_role_when_it_uses_bare_replication_pair(self):
        primary = distribution("primary", f"staging.{BUCKET}")
        primary["Aliases"] = {"Items": [BUCKET]}
        staging = distribution("staging", BUCKET, True)
        with patch.object(
            deploy_content,
            "fetch_distributions",
            return_value={"DistributionList": {"Items": [primary, staging]}},
        ):
            matches = deploy_content.find_project_distributions(BUCKET)
        self.assertEqual(matches["production"]["Id"], "primary")
        self.assertEqual(matches["staging"]["Id"], "staging")

    def test_deployment_target_alternates_by_exact_origin_pair_after_flip(self):
        for active_family, expected in (
            (BUCKET, f"staging.{BUCKET}"),
            (f"staging.{BUCKET}", BUCKET),
        ):
            production = distribution("primary", active_family)
            inactive_family = f"staging.{BUCKET}" if active_family == BUCKET else BUCKET
            staging = distribution("staging", inactive_family, True)
            with patch.dict(os.environ, {"ENABLE_CLOUDFRONT_STAGING": "true"}), patch.object(
                deploy_content,
                "find_project_distributions",
                return_value={"production": production, "staging": staging},
            ):
                self.assertEqual(deploy_content.determine_deployment_target(BUCKET), expected)

    def test_deployment_target_rejects_same_pair_partial_promotion_before_upload(self):
        both_primary = {
            "production": distribution("primary", BUCKET),
            "staging": distribution("staging", BUCKET, True),
        }
        with patch.dict(os.environ, {"BUCKET_NAME": BUCKET, "ENABLE_CLOUDFRONT_STAGING": "true"}), patch.object(
            deploy_content, "find_project_distributions", return_value=both_primary
        ), patch.object(deploy_content, "deploy_files") as upload:
            with self.assertRaisesRegex(ValueError, "opposite exact CRM"):
                deploy_content.main()
        upload.assert_not_called()

    def test_deploy_uses_build_dir_and_sets_html_and_hashed_cache_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "index.html").write_text("<html></html>", encoding="utf-8")
            (root / "main.0123456789abcdef.js").write_text("bundle", encoding="utf-8")
            (root / "logo.svg").write_text("svg", encoding="utf-8")
            with patch.object(deploy_content, "BUILD_DIR", temp_dir), patch.object(
                deploy_content.subprocess, "check_output", return_value="ok"
            ) as run:
                deploy_content.deploy_files(BUCKET)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[0][3], temp_dir)
            self.assertIn("public,max-age=0,must-revalidate", commands[0])
            self.assertEqual(len(commands), 3)
            self.assertEqual(commands[1][2], "cp")
            self.assertIn("public,max-age=0,must-revalidate", commands[1])
            self.assertIn("public,max-age=31536000,immutable", commands[2])
            self.assertTrue(commands[2][4].endswith("main.0123456789abcdef.js"))

    def test_manifest_contains_required_origin_mapping_and_build_identity(self):
        primary = distribution("primary", BUCKET)
        staging = distribution("staging", f"staging.{BUCKET}", True)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "index.html").write_bytes(b"app-shell")
            manifest_path = root / "manifest.json"
            with patch.dict(
                os.environ,
                {
                    "BUCKET_NAME": BUCKET,
                    "ENABLE_CLOUDFRONT_STAGING": "true",
                    "CRM_SOURCE_VERSION": "crm-revision-123",
                },
            ), patch.object(deploy_content, "BUILD_DIR", temp_dir), patch.object(
                deploy_content, "DEPLOYMENT_MANIFEST", str(manifest_path)
            ), patch.object(
                deploy_content,
                "find_project_distributions",
                return_value={"production": primary, "staging": staging},
            ), patch.object(deploy_content, "deploy_files"):
                deploy_content.main()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["target_bucket"], f"staging.{BUCKET}")
        self.assertEqual(manifest["origins"]["primary"], staging["Origins"])
        self.assertEqual(manifest["origins"]["staging"], primary["Origins"])
        self.assertEqual(manifest["crm_source_revision"], "crm-revision-123")
        self.assertEqual(manifest["index_sha256"], "b4ed9632452fd12fd6297fbb3b74808b35f3b4e5a833df459e49ad16d08a41aa")

    def test_direct_mode_still_emits_healthcheck_manifest_with_real_crm_revision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "index.html").write_bytes(b"direct-shell")
            manifest_path = root / "manifest.json"
            with patch.dict(
                os.environ,
                {"BUCKET_NAME": BUCKET, "ENABLE_CLOUDFRONT_STAGING": "false", "CRM_SOURCE_VERSION": "crm-direct-rev"},
            ), patch.object(deploy_content, "BUILD_DIR", temp_dir), patch.object(
                deploy_content, "DEPLOYMENT_MANIFEST", str(manifest_path)
            ), patch.object(
                deploy_content, "find_project_distributions", side_effect=AssertionError("direct mode must not inspect CloudFront")
            ), patch.object(deploy_content, "deploy_files"):
                deploy_content.main()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["target_bucket"], BUCKET)
        self.assertEqual(manifest["crm_source_revision"], "crm-direct-rev")
        self.assertEqual(manifest["index_sha256"], hashlib.sha256(b"direct-shell").hexdigest())
        self.assertNotIn("origins", manifest)

        with patch.dict(
            os.environ,
            {"BUCKET_NAME": BUCKET, "CLOUDFRONT_REGION": "us-east-1", "ENABLE_CLOUDFRONT_STAGING": "false"},
        ):
            swapper = origin_change.CloudFrontOriginSwapper()
            with patch.object(swapper, "_filter_distributions", side_effect=AssertionError("direct release must not inspect CloudFront")), patch.object(
                swapper, "_update_distribution"
            ) as update:
                swapper.execute_origin_swap(manifest)
        update.assert_not_called()

    def test_direct_mode_rejects_incomplete_healthcheck_manifest(self):
        with patch.dict(
            os.environ,
            {"BUCKET_NAME": BUCKET, "CLOUDFRONT_REGION": "us-east-1", "ENABLE_CLOUDFRONT_STAGING": "false"},
        ):
            swapper = origin_change.CloudFrontOriginSwapper()
            with self.assertRaisesRegex(origin_change.CloudFrontOriginSwapError, "index_sha256"):
                swapper.execute_origin_swap({"target_bucket": BUCKET, "crm_source_revision": "rev"})

    def test_manifest_generation_requires_crm_revision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "index.html").write_text("shell", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"BUCKET_NAME": BUCKET, "ENABLE_CLOUDFRONT_STAGING": "false"},
                clear=True,
            ), patch.object(deploy_content, "BUILD_DIR", temp_dir), patch.object(
                deploy_content, "deploy_files"
            ) as deploy:
                with self.assertRaisesRegex(RuntimeError, "CRM_SOURCE_VERSION"):
                    deploy_content.main()
            deploy.assert_not_called()

    def test_manifest_promotion_reconciles_only_drifted_distribution(self):
        blue = distribution("primary", BUCKET)["Origins"]
        green = distribution("staging", f"staging.{BUCKET}", True)["Origins"]
        manifest = {
            "target_bucket": f"staging.{BUCKET}",
            "crm_source_revision": "crm-test-rev",
            "index_sha256": "a" * 64,
            "origins": {"primary": green, "staging": blue},
        }
        configs = [
            {"ETag": "etag", "DistributionConfig": {"Origins": blue}},
            {"ETag": "etag", "DistributionConfig": {"Origins": blue}},
        ]
        with patch.dict(
            os.environ,
            {"BUCKET_NAME": BUCKET, "CLOUDFRONT_REGION": "us-east-1", "ENABLE_CLOUDFRONT_STAGING": "true"},
        ):
            swapper = origin_change.CloudFrontOriginSwapper()
            with patch.object(swapper, "_filter_distributions", return_value=(["primary", "staging"], configs)), patch.object(
                swapper, "_update_distribution"
            ) as update, patch.object(origin_change.subprocess, "check_call") as wait:
                swapper.execute_origin_swap(manifest)
        self.assertEqual([call.args[0] for call in update.call_args_list], ["primary"])
        self.assertEqual(wait.call_count, 2)

        configs[0]["DistributionConfig"]["Origins"] = green
        configs[1]["DistributionConfig"]["Origins"] = green
        with patch.dict(
            os.environ,
            {"BUCKET_NAME": BUCKET, "CLOUDFRONT_REGION": "us-east-1", "ENABLE_CLOUDFRONT_STAGING": "true"},
        ):
            swapper = origin_change.CloudFrontOriginSwapper()
            with patch.object(swapper, "_filter_distributions", return_value=(["primary", "staging"], configs)), patch.object(
                swapper, "_update_distribution"
            ) as update, patch.object(origin_change.subprocess, "check_call"):
                swapper.execute_origin_swap(manifest)
        self.assertEqual([call.args[0] for call in update.call_args_list], ["staging"])

    def test_origin_filter_orders_primary_and_staging_by_role_not_origin_family(self):
        primary = distribution("primary", f"staging.{BUCKET}")
        primary["Aliases"] = {"Items": [BUCKET]}
        staging = distribution("staging", BUCKET, True)
        configs = {
            "staging": {"ETag": "s", "DistributionConfig": staging},
            "primary": {"ETag": "p", "DistributionConfig": primary},
        }
        with patch.dict(os.environ, {"BUCKET_NAME": BUCKET, "CLOUDFRONT_REGION": "us-east-1"}):
            swapper = origin_change.CloudFrontOriginSwapper()
            swapper._distribution_metadata = {
                "staging": {"Staging": True},
                "primary": {"Staging": False},
            }
            with patch.object(swapper, "_fetch_distribution_ids", return_value=["staging", "primary"]), patch.object(
                swapper, "_fetch_distribution_config", side_effect=lambda identifier: configs[identifier]
            ):
                identifiers, ordered_configs = swapper._filter_distributions()
        self.assertEqual(identifiers, ["primary", "staging"])
        self.assertEqual(ordered_configs, [configs["primary"], configs["staging"]])

    def test_origin_promotion_fails_closed_without_manifest(self):
        with patch.dict(
            os.environ,
            {"BUCKET_NAME": BUCKET, "CLOUDFRONT_REGION": "us-east-1", "ENABLE_CLOUDFRONT_STAGING": "true"},
        ):
            swapper = origin_change.CloudFrontOriginSwapper()
            with self.assertRaises(origin_change.CloudFrontOriginSwapError):
                swapper.execute_origin_swap()

    def test_explicit_rollback_retains_legacy_origin_swap(self):
        configs = [
            {"ETag": "etag", "DistributionConfig": {"Origins": {"Items": [{"DomainName": "blue"}]}}},
            {"ETag": "etag", "DistributionConfig": {"Origins": {"Items": [{"DomainName": "green"}]}}},
        ]
        with patch.dict(
            os.environ,
            {
                "BUCKET_NAME": BUCKET,
                "CLOUDFRONT_REGION": "us-east-1",
                "ENABLE_CLOUDFRONT_STAGING": "true",
                "ROLLBACK": "true",
            },
        ):
            swapper = origin_change.CloudFrontOriginSwapper()
            with patch.object(swapper, "_filter_distributions", return_value=(["primary", "staging"], configs)), patch.object(
                swapper, "_update_distribution"
            ) as update, patch.object(origin_change.subprocess, "check_call") as wait:
                swapper.execute_origin_swap()
        self.assertEqual(update.call_count, 2)
        self.assertEqual(wait.call_count, 2)

    def test_cache_invalidation_uses_exact_bucket_and_cloudfront_staging_flag(self):
        invalidator = cache_invalidation.CloudFrontCacheInvalidator()
        with patch.dict(os.environ, {"BUCKET_NAME": BUCKET}):
            self.assertEqual(
                invalidator._classify_distribution(distribution("web", "vilnacrm.example")), None
            )
            self.assertEqual(
                invalidator._classify_distribution(distribution("primary", BUCKET)),
                cache_invalidation.Environment.PRODUCTION,
            )
            self.assertEqual(
                invalidator._classify_distribution(distribution("staging", BUCKET, True)),
                cache_invalidation.Environment.STAGING,
            )
            # The role stays staging even when its exact origin pair is the bare pair after promotion.
            flipped_staging = distribution("staging", BUCKET, True)
            self.assertEqual(
                invalidator._classify_distribution(flipped_staging),
                cache_invalidation.Environment.STAGING,
            )
            incomplete = distribution("incomplete", BUCKET)
            incomplete["Origins"]["Items"] = incomplete["Origins"]["Items"][:1]
            self.assertIsNone(invalidator._classify_distribution(incomplete))

    def test_cache_invalidation_rejects_duplicate_exact_primary_distributions(self):
        first = distribution("primary-a", BUCKET)
        second = distribution("primary-b", BUCKET)
        invalidator = cache_invalidation.CloudFrontCacheInvalidator()
        invalidator.enable_cloudfront_staging = False
        with patch.dict(os.environ, {"BUCKET_NAME": BUCKET}), patch.object(
            invalidator, "_fetch_all_distributions", return_value=[first, second]
        ), self.assertRaises(cache_invalidation.CloudFrontInvalidationError):
            invalidator.find_distributions_by_environment()

    def test_policy_switch_reads_policy_id_from_primary_config(self):
        primary = distribution("primary", BUCKET)
        staging = distribution("staging", f"staging.{BUCKET}", True)
        policy_config = {
            "StagingDistributionDnsNames": {"Quantity": 1, "Items": [staging["DomainName"]]},
            "Enabled": True,
            "TrafficConfig": {"Type": "SingleHeader", "SingleHeaderConfig": {"Header": "aws-cf-cd-canary", "Value": "canary"}},
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "BUCKET_NAME": BUCKET,
                "CLOUDFRONT_REGION": "us-east-1",
                "CLOUDFRONT_HEADER": "canary",
                "CLOUDFRONT_WEIGHT": "0.1",
                "ENABLE_CLOUDFRONT_STAGING": "true",
            },
        ), patch.object(policy, "find_project_distributions", return_value={"production": primary, "staging": staging}), patch.object(
            policy.subprocess,
            "check_output",
            return_value=json.dumps({"DistributionConfig": {"ContinuousDeploymentPolicyId": "crm-policy"}}).encode(),
        ) as command, patch.object(
            policy, "fetch_continuous_deployment_policy", return_value={"ETag": "etag", "ContinuousDeploymentPolicy": {"ContinuousDeploymentPolicyConfig": policy_config}}
        ) as fetch, patch.object(policy, "update_continuous_deployment_policy") as update, patch.object(
            policy.subprocess, "check_call"
        ) as wait, patch.object(policy, "CONFIG_FILENAME", str(Path(temp_dir) / "policy.json")):
            policy.main()
        self.assertIn("primary", command.call_args.args[0])
        fetch.assert_called_once_with("crm-policy", "us-east-1")
        update.assert_not_called()
        self.assertEqual(wait.call_count, 2)

    def test_distribution_policy_attachment_targets_exact_primary(self):
        primary = distribution("crm-primary", BUCKET)
        with patch.dict(os.environ, {"BUCKET_NAME": BUCKET}), patch.object(
            distribution_deploy, "continuous_deployment_id", "crm-policy"
        ), patch.object(distribution_deploy, "production_distribution_id", None), patch.object(
            distribution_deploy,
            "find_project_distributions",
            return_value={"production": primary, "staging": distribution("other", f"staging.{BUCKET}", True)},
        ), patch.object(
            distribution_deploy, "fetch_production_distribution_config", return_value={"ETag": "etag"}
        ) as fetch, patch.object(distribution_deploy, "update_production_distribution_config") as update:
            distribution_deploy.main()
        fetch.assert_called_once_with("crm-primary")
        update.assert_called_once_with({"ETag": "etag"}, "crm-primary")


if __name__ == "__main__":
    unittest.main()
