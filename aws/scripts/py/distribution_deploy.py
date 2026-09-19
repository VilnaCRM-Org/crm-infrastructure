import json
import subprocess
import os

from deploy_content import find_project_distributions

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(_path):
        return False

load_dotenv("./.terraform.env")

CLOUDFRONT_REGION = os.environ.get("CLOUDFRONT_REGION", "")
config_filename = "distribution_config.json"
continuous_deployment_id = os.getenv("CONTINUOUS_DEPLOYMENT_ID")
production_distribution_id = os.getenv("PRODUCTION_DISTRIBUTION_ID")


def fetch_production_distribution_config(distribution_id=None):
    print("Fetching production distribution configuration...")
    config_result = subprocess.check_output(
        [
            "aws",
            "cloudfront",
            "get-distribution-config",
            "--id",
            distribution_id or production_distribution_id,
            "--region",
            CLOUDFRONT_REGION,
            "--no-cli-pager",
        ]
    )
    config_json = json.loads(config_result.decode())
    print(f"Fetched production distribution configuration: {config_json}")
    return config_json


def update_production_distribution_config(config_json, distribution_id=None):
    print("Updating production distribution configuration...")
    etag = config_json["ETag"]
    config_json["DistributionConfig"][
        "ContinuousDeploymentPolicyId"
    ] = continuous_deployment_id

    with open(config_filename, "w") as text_file:
        text_file.write(json.dumps(config_json["DistributionConfig"]))

    subprocess.check_output(
        [
            "aws",
            "cloudfront",
            "update-distribution",
            "--id",
            distribution_id or production_distribution_id,
            "--distribution-config",
            f"file://{config_filename}",
            "--region",
            CLOUDFRONT_REGION,
            "--if-match",
            etag,
        ]
    )
    print(
        f"Updated production distribution configuration with ID {distribution_id or production_distribution_id}"
    )


def main():
    print("Starting main function...")
    if not continuous_deployment_id:
        print(
            "No continuous deployment policy configured, skipping distribution update"
        )
        return
    configured_distribution_id = production_distribution_id
    if not configured_distribution_id:
        bucket_name = os.environ.get("BUCKET_NAME")
        if not bucket_name:
            raise RuntimeError("BUCKET_NAME is required to identify the CRM primary distribution")
        distributions = find_project_distributions(bucket_name)
        production = distributions["production"]
        if not production:
            raise RuntimeError("Could not identify the CRM primary distribution")
        configured_distribution_id = production["Id"]
    else:
        bucket_name = os.environ.get("BUCKET_NAME")
        if not bucket_name:
            raise RuntimeError("BUCKET_NAME is required to validate the CRM primary distribution")
        production = find_project_distributions(bucket_name)["production"]
        if not production or production["Id"] != configured_distribution_id:
            raise RuntimeError("PRODUCTION_DISTRIBUTION_ID does not match the CRM primary distribution")
    production_config = fetch_production_distribution_config(configured_distribution_id)
    update_production_distribution_config(production_config, configured_distribution_id)
    print("Main function completed.")


if __name__ == "__main__":
    main()
