import json
import subprocess
import os

from deploy_content import find_project_distributions

MAX_ITEMS = "1"
CONFIG_FILENAME = "continuous_deployment_policy.json"

CLOUDFRONT_WEIGHT = os.environ.get("CLOUDFRONT_WEIGHT", "")
CLOUDFRONT_HEADER = os.environ.get("CLOUDFRONT_HEADER", "")
CLOUDFRONT_REGION = os.environ.get("CLOUDFRONT_REGION", "")
CLF_TYPE_ENV_VAR = "CLOUDFRONT_TYPE"
CLOUDFRONT_TYPE = os.environ.get(CLF_TYPE_ENV_VAR, "SingleHeader")
ENABLE_CLOUDFRONT_STAGING = os.environ.get(
    "ENABLE_CLOUDFRONT_STAGING", ""
).strip().lower() not in {"false", "0", "no"}


def create_config(staging_dns_name, config_value=None, config_type="weight"):
    config_value = config_value or CLOUDFRONT_WEIGHT
    config_type = config_type or CLOUDFRONT_TYPE
    config_type = {"weight": "SingleWeight", "header": "SingleHeader"}.get(
        config_type.strip(), config_type.strip()
    )
    print(
        f"Creating config with staging_dns_name: {staging_dns_name}, "
        f"config_type: {config_type}"
    )

    valid_types = {"SingleWeight", "SingleHeader"}
    if config_type not in valid_types:
        raise ValueError(
            f"Unsupported continuous deployment type '{config_type}'. "
            f"Expected one of {sorted(valid_types)}. "
            f"Set the {CLF_TYPE_ENV_VAR} environment variable accordingly."
        )

    print(f"Using config value: {config_value}")
    base_config = {
        "StagingDistributionDnsNames": {"Quantity": 1, "Items": [staging_dns_name]},
        "Enabled": True,
        "TrafficConfig": {"Type": config_type},
    }

    if config_type == "SingleWeight":
        base_config["TrafficConfig"]["SingleWeightConfig"] = {
            "Weight": float(config_value)
        }
    else:  # config_type == "SingleHeader"
        base_config["TrafficConfig"]["SingleHeaderConfig"] = {
            "Header": f"aws-cf-cd-{config_value}",
            "Value": config_value,
        }

    print(f"Created config: {base_config}")
    return base_config


def fetch_continuous_deployment_policies(cloudfront_region=None):
    print("Fetching continuous deployment policies")
    result = subprocess.check_output(
        [
            "aws",
            "cloudfront",
            "list-continuous-deployment-policies",
            "--region",
            cloudfront_region or CLOUDFRONT_REGION,
            "--no-cli-pager",
            "--max-items",
            MAX_ITEMS,
        ]
    )
    policies = json.loads(result.decode())
    print(f"Fetched policies: {policies}")
    return policies


def fetch_continuous_deployment_policy(id, cloudfront_region=None):
    print(f"Fetching continuous deployment policy with id: {id}")
    result = subprocess.check_output(
        [
            "aws",
            "cloudfront",
            "get-continuous-deployment-policy",
            "--region",
            cloudfront_region or CLOUDFRONT_REGION,
            "--no-cli-pager",
            "--id",
            id,
        ]
    )
    policy = json.loads(result.decode())
    print(f"Fetched policy: {policy}")
    return policy


def update_continuous_deployment_policy(
    policy_id, policy_etag, config_filename, cloudfront_region=None
):
    print(
        f"Updating continuous deployment policy with id: {policy_id}, "
        f"etag: {policy_etag}, config_filename: {config_filename}"
    )
    subprocess.check_output(
        [
            "aws",
            "cloudfront",
            "update-continuous-deployment-policy",
            "--id",
            policy_id,
            "--continuous-deployment-policy-config",
            f"file://{config_filename}",
            "--region",
            cloudfront_region or CLOUDFRONT_REGION,
            "--if-match",
            policy_etag,
        ]
    )
    print(f"Updated policy with id: {policy_id}")


def main():
    print("Starting main function")
    if not ENABLE_CLOUDFRONT_STAGING:
        print("CloudFront staging is disabled, skipping continuous deployment switch")
        return
    required_env = {
        "BUCKET_NAME": os.environ.get("BUCKET_NAME"),
        "CLOUDFRONT_WEIGHT": os.environ.get("CLOUDFRONT_WEIGHT"),
        "CLOUDFRONT_HEADER": os.environ.get("CLOUDFRONT_HEADER"),
        "CLOUDFRONT_REGION": os.environ.get("CLOUDFRONT_REGION"),
    }
    missing = [name for name, value in required_env.items() if not value]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))

    distributions = find_project_distributions(required_env["BUCKET_NAME"])
    production = distributions["production"]
    staging = distributions["staging"]
    if not production or not staging:
        raise RuntimeError("Both CRM primary and staging distributions are required")

    primary_response = subprocess.check_output(
        [
            "aws", "cloudfront", "get-distribution-config", "--id", production["Id"],
            "--region", required_env["CLOUDFRONT_REGION"], "--no-cli-pager",
        ]
    )
    policy_item_id = json.loads(primary_response.decode())["DistributionConfig"].get(
        "ContinuousDeploymentPolicyId"
    )
    if not policy_item_id:
        raise RuntimeError("CRM primary distribution has no continuous deployment policy")
    print(f"Policy item id: {policy_item_id}")

    policy = fetch_continuous_deployment_policy(policy_item_id, required_env["CLOUDFRONT_REGION"])
    policy_etag = policy["ETag"]
    policy_config = policy["ContinuousDeploymentPolicy"][
        "ContinuousDeploymentPolicyConfig"
    ]
    staging_dns_name = policy_config["StagingDistributionDnsNames"]["Items"][0]
    if staging_dns_name != staging.get("DomainName"):
        raise RuntimeError("CRM deployment policy points to another staging distribution")
    print(
        f"Policy ETag: {policy_etag}, Staging DNS Name: {staging_dns_name}, "
        f"Current Config Type: {policy_config['TrafficConfig']['Type']}, "
        f"Desired Config Type: {CLOUDFRONT_TYPE}"
    )

    continuous_deployment_policy = create_config(
        staging_dns_name, required_env["CLOUDFRONT_HEADER"], "header"
    )

    if policy_config == continuous_deployment_policy:
        print("CRM staging policy is already header-only")
    else:
        with open(CONFIG_FILENAME, "w") as config_file:
            print(f"Writing config to {CONFIG_FILENAME}")
            json.dump(continuous_deployment_policy, config_file, indent=4)

        update_continuous_deployment_policy(
            policy_item_id, policy_etag, CONFIG_FILENAME, required_env["CLOUDFRONT_REGION"]
        )
    for distribution in (production, staging):
        subprocess.check_call(
            [
                "aws", "cloudfront", "wait", "distribution-deployed", "--id",
                distribution["Id"], "--region", required_env["CLOUDFRONT_REGION"],
            ]
        )
    print("Main function completed")


if __name__ == "__main__":
    main()
