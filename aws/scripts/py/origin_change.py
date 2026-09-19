#!/usr/bin/env python3
"""
CloudFront Origin Swap Script for CRM

Swaps origins between two CloudFront CRM app distributions.
This is typically used for blue-green deployments.
Targets distributions with "app." in their domain names.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from deploy_content import origin_pair_role


class CloudFrontOriginSwapError(Exception):
    """CloudFront origin swap operation error"""


def validate_manifest_identity(deployment: dict[str, Any]) -> None:
    revision = deployment.get("crm_source_revision")
    digest = deployment.get("index_sha256")
    if not isinstance(revision, str) or not revision.strip():
        raise CloudFrontOriginSwapError(
            "Deployment manifest is missing crm_source_revision"
        )
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest.lower())
    ):
        raise CloudFrontOriginSwapError(
            "Deployment manifest has an invalid index_sha256"
        )


class CloudFrontOriginSwapper:
    """Handles CloudFront origin swapping operations"""

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.region = self._get_region()
        self.enable_cloudfront_staging = os.environ.get(
            "ENABLE_CLOUDFRONT_STAGING", ""
        ).strip().lower() not in {"false", "0", "no"}

    def _get_region(self) -> str:
        """Get CloudFront region from environment variable"""
        region = os.environ.get("CLOUDFRONT_REGION")
        if not region:
            raise CloudFrontOriginSwapError(
                "CLOUDFRONT_REGION environment variable is required",
            )
        return region

    def _run_aws_command(self, command: list[str]) -> dict[str, Any]:
        """Run AWS CLI command and return parsed JSON result"""
        try:
            self.logger.debug("Running: %s", " ".join(command))
            result = subprocess.check_output(
                command,
                stderr=subprocess.STDOUT,
                text=True,
            )
            return json.loads(result)
        except subprocess.CalledProcessError as e:
            raise CloudFrontOriginSwapError(f"AWS CLI failed: {e.output}") from e
        except json.JSONDecodeError as e:
            raise CloudFrontOriginSwapError("Failed to parse AWS CLI response") from e

    def _fetch_distribution_ids(self) -> list[str]:
        """Fetch all CloudFront distribution IDs"""
        self.logger.info("Fetching distribution IDs...")

        result = self._run_aws_command(
            [
                "aws",
                "cloudfront",
                "list-distributions",
                "--region",
                self.region,
                "--no-cli-pager",
            ],
        )

        items = result["DistributionList"]["Items"]
        self._distribution_metadata = {item["Id"]: item for item in items}
        distribution_ids = [item["Id"] for item in items]
        self.logger.info("Found %d distributions", len(distribution_ids))
        return distribution_ids

    def _fetch_distribution_config(self, distribution_id: str) -> dict[str, Any]:
        """Fetch configuration for a single distribution"""
        return self._run_aws_command(
            [
                "aws",
                "cloudfront",
                "get-distribution-config",
                "--id",
                distribution_id,
                "--region",
                self.region,
                "--no-cli-pager",
            ],
        )

    def _should_skip_distribution(
        self,
        distribution_id: str,
        config: dict[str, Any],
    ) -> bool:
        """Check if distribution should be skipped (should target app distributions for CRM)"""
        dist_config = config["DistributionConfig"]

        bucket = os.environ.get("BUCKET_NAME", "")
        if not bucket:
            raise CloudFrontOriginSwapError(
                "BUCKET_NAME environment variable is required"
            )
        origins = dist_config.get("Origins", {}).get("Items", [])
        if origin_pair_role(origins, bucket) is None:
            self.logger.info(
                "Skipping distribution %s outside the exact CRM bucket pairs",
                distribution_id,
            )
            return True
        return False

    def _filter_distributions(self) -> tuple[list[str], list[dict[str, Any]]]:
        """Fetch and filter distributions, targeting app distributions for CRM"""
        self.logger.info("Filtering distributions for CRM app distributions...")

        distribution_ids = self._fetch_distribution_ids()
        filtered_configs, filtered_ids = [], []

        for dist_id in distribution_ids:
            config = self._fetch_distribution_config(dist_id)
            if not self._should_skip_distribution(dist_id, config):
                filtered_configs.append(config)
                filtered_ids.append(dist_id)

        self.logger.info("Filtered to %d CRM app distributions", len(filtered_configs))

        if len(filtered_configs) != 2:
            raise CloudFrontOriginSwapError(
                f"Expected exactly 2 CRM app distributions for origin swap, "
                f"but found {len(filtered_configs)}. Check your CloudFront configuration.",
            )

        bucket = os.environ["BUCKET_NAME"]
        primary_ids = []
        staging_ids = []
        for dist_id, config in zip(filtered_ids, filtered_configs):
            listed = self._distribution_metadata.get(dist_id, {})
            if listed.get("Staging", False):
                staging_ids.append((dist_id, config))
                continue
            aliases = config["DistributionConfig"].get("Aliases", {}).get("Items", [])
            if bucket in aliases or f"www.{bucket}" in aliases:
                primary_ids.append((dist_id, config))
        if len(primary_ids) != 1 or len(staging_ids) != 1:
            raise CloudFrontOriginSwapError(
                "Expected exactly one primary and one staging CRM distribution "
                f"(found primary={len(primary_ids)}, staging={len(staging_ids)})"
            )
        ordered = [primary_ids[0], staging_ids[0]]
        return [item[0] for item in ordered], [item[1] for item in ordered]

    def _swap_origins(self, configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Swap origins between two distribution configurations"""
        self.logger.info("Swapping origins...")

        config1, config2 = configs
        origins1 = config1["DistributionConfig"].get("Origins")
        origins2 = config2["DistributionConfig"].get("Origins")

        if origins1 and origins2:
            config1["DistributionConfig"]["Origins"] = origins2
            config2["DistributionConfig"]["Origins"] = origins1

        self.logger.info("Origins swapped successfully")
        return configs

    def _update_distribution(
        self,
        distribution_id: str,
        config: dict[str, Any],
    ) -> None:
        """Update a single distribution configuration"""
        etag = config["ETag"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config["DistributionConfig"], f, indent=2)
            temp_path = f.name

        try:
            self._run_aws_command(
                [
                    "aws",
                    "cloudfront",
                    "update-distribution",
                    "--id",
                    distribution_id,
                    "--distribution-config",
                    f"file://{temp_path}",
                    "--region",
                    self.region,
                    "--if-match",
                    etag,
                ],
            )
            self.logger.info("Updated distribution %s", distribution_id)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def execute_origin_swap(self, deployment: dict[str, Any] | None = None) -> None:
        """Execute the complete origin swap process"""
        self.logger.info("Starting CloudFront origin swap...")

        try:
            rollback = os.environ.get("ROLLBACK", "").strip().lower() == "true"
            if not self.enable_cloudfront_staging:
                if rollback and deployment is None:
                    self.logger.info(
                        "Rollback requested with CloudFront staging disabled; no origin change"
                    )
                    return
                if deployment is None:
                    raise CloudFrontOriginSwapError(
                        "A deployment manifest is required to validate direct-mode release"
                    )
                validate_manifest_identity(deployment)
                if deployment.get("target_bucket") != os.environ.get("BUCKET_NAME"):
                    raise CloudFrontOriginSwapError(
                        "Direct-mode release manifest must target the CRM primary bucket"
                    )
                self.logger.info(
                    "CloudFront staging is disabled; validated direct-mode manifest without origin changes"
                )
                return

            if deployment is None:
                if not rollback:
                    raise CloudFrontOriginSwapError(
                        "A deployment manifest is required to promote CRM content"
                    )
                distribution_ids, configs = self._filter_distributions()
                updated_configs = self._swap_origins(configs)
                for dist_id, config in zip(distribution_ids, updated_configs):
                    self._update_distribution(dist_id, config)
                for dist_id in distribution_ids:
                    subprocess.check_call(
                        [
                            "aws",
                            "cloudfront",
                            "wait",
                            "distribution-deployed",
                            "--id",
                            dist_id,
                            "--region",
                            self.region,
                        ]
                    )
                self.logger.info("CloudFront rollback origin swap completed")
                return
            validate_manifest_identity(deployment)
            bucket = os.environ["BUCKET_NAME"]
            target_bucket = deployment.get("target_bucket")
            if target_bucket not in {bucket, f"staging.{bucket}"}:
                raise CloudFrontOriginSwapError(
                    f"Deployment manifest target bucket {target_bucket!r} is not a CRM bucket"
                )

            distribution_ids, configs = self._filter_distributions()
            desired_origins = deployment.get("origins")
            if not isinstance(desired_origins, dict) or set(desired_origins) != {
                "primary",
                "staging",
            }:
                raise CloudFrontOriginSwapError(
                    "Deployment manifest must include primary and staging origins"
                )
            desired_by_id = dict(
                zip(
                    distribution_ids,
                    (desired_origins["primary"], desired_origins["staging"]),
                )
            )
            expected_primary_role = "primary" if target_bucket == bucket else "staging"
            expected_staging_role = "staging" if target_bucket == bucket else "primary"
            if (
                origin_pair_role(desired_origins["primary"].get("Items", []), bucket)
                != expected_primary_role
                or origin_pair_role(desired_origins["staging"].get("Items", []), bucket)
                != expected_staging_role
            ):
                raise CloudFrontOriginSwapError(
                    "Deployment manifest origins must map the correct CRM base and "
                    "replication buckets to primary and staging"
                )

            for dist_id, config in zip(distribution_ids, configs):
                desired = desired_by_id[dist_id]
                if config["DistributionConfig"].get("Origins") != desired:
                    config["DistributionConfig"]["Origins"] = desired
                    self._update_distribution(dist_id, config)

            for dist_id in distribution_ids:
                subprocess.check_call(
                    [
                        "aws",
                        "cloudfront",
                        "wait",
                        "distribution-deployed",
                        "--id",
                        dist_id,
                        "--region",
                        self.region,
                    ]
                )

            self.logger.info("Origin swap completed successfully")

        except Exception as e:
            self.logger.exception("Origin swap failed: %s", type(e).__name__)
            raise


def setup_logging(level: str = "INFO") -> None:
    """Configure logging"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="CloudFront origin swap for CRM blue-green deployments",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level",
    )
    parser.add_argument(
        "--deployment-manifest",
        default=os.environ.get("DEPLOYMENT_MANIFEST", "deployment_manifest.json"),
        help="Artifact describing the intended CRM primary/staging origins",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    try:
        swapper = CloudFrontOriginSwapper()
        if os.environ.get("ROLLBACK", "").strip().lower() == "true":
            manifest = None
        else:
            manifest = json.loads(
                Path(args.deployment_manifest).read_text(encoding="utf-8")
            )
        swapper.execute_origin_swap(manifest)
    except CloudFrontOriginSwapError:
        logger.exception("CloudFront origin swap error")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Process interrupted")
        sys.exit(130)
    except Exception as e:
        logger.exception("Unexpected error: %s", type(e).__name__)
        sys.exit(1)


if __name__ == "__main__":
    main()
