import json
import subprocess
import os

MAX_ITEMS = "1"
CONFIG_FILENAME = "continuous_deployment_policy.json"

CLOUDFRONT_WEIGHT = os.environ["CLOUDFRONT_WEIGHT"]
CLOUDFRONT_HEADER = os.environ["CLOUDFRONT_HEADER"]
CLOUDFRONT_REGION = os.environ["CLOUDFRONT_REGION"]
CLF_TYPE_ENV_VAR = "CLOUDFRONT_TYPE"
CLOUDFRONT_TYPE = os.environ.get(CLF_TYPE_ENV_VAR, "SingleHeader")


def create_config(staging_dns_name):
    config_type = CLOUDFRONT_TYPE.strip()
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

    print(
        f"Using parameters — weight: {CLOUDFRONT_WEIGHT}, header: {CLOUDFRONT_HEADER}"
    )
    base_config = {
        "StagingDistributionDnsNames": {"Quantity": 1, "Items": [staging_dns_name]},
        "Enabled": True,
        "TrafficConfig": {"Type": config_type},
    }

    if config_type == "SingleWeight":
        base_config["TrafficConfig"]["SingleWeightConfig"] = {
            "Weight": float(CLOUDFRONT_WEIGHT)
        }
    else:  # config_type == "SingleHeader"
        base_config["TrafficConfig"]["SingleHeaderConfig"] = {
            "Header": f"aws-cf-cd-{CLOUDFRONT_HEADER}",
            "Value": CLOUDFRONT_HEADER,
        }

    print(f"Created config: {base_config}")
    return base_config


def fetch_continuous_deployment_policies():
    print("Fetching continuous deployment policies")
    result = subprocess.check_output(
        [
            "aws",
            "cloudfront",
            "list-continuous-deployment-policies",
            "--region",
            CLOUDFRONT_REGION,
            "--no-cli-pager",
            "--max-items",
            MAX_ITEMS,
        ]
    )
    policies = json.loads(result.decode())
    print(f"Fetched policies: {policies}")
    return policies


def fetch_continuous_deployment_policy(id):
    print(f"Fetching continuous deployment policy with id: {id}")
    result = subprocess.check_output(
        [
            "aws",
            "cloudfront",
            "get-continuous-deployment-policy",
            "--region",
            CLOUDFRONT_REGION,
            "--no-cli-pager",
            "--id",
            id,
        ]
    )
    policy = json.loads(result.decode())
    print(f"Fetched policy: {policy}")
    return policy


def update_continuous_deployment_policy(policy_id, policy_etag, config_filename):
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
            CLOUDFRONT_REGION,
            "--if-match",
            policy_etag,
        ]
    )
    print(f"Updated policy with id: {policy_id}")


def main():
    print("Starting main function")
    policies_list = fetch_continuous_deployment_policies()
    policy_item = policies_list["ContinuousDeploymentPolicyList"]["Items"][0][
        "ContinuousDeploymentPolicy"
    ]
    policy_item_id = policy_item["Id"]
    print(f"Policy item id: {policy_item_id}")

    policy = fetch_continuous_deployment_policy(policy_item_id)
    policy_etag = policy["ETag"]
    policy_config = policy["ContinuousDeploymentPolicy"][
        "ContinuousDeploymentPolicyConfig"
    ]
    staging_dns_name = policy_config["StagingDistributionDnsNames"]["Items"][0]
    print(
        f"Policy ETag: {policy_etag}, Staging DNS Name: {staging_dns_name}, "
        f"Current Config Type: {policy_config['TrafficConfig']['Type']}, "
        f"Desired Config Type: {CLOUDFRONT_TYPE}"
    )

    continuous_deployment_policy = create_config(staging_dns_name)

    with open(CONFIG_FILENAME, "w") as config_file:
        print(f"Writing config to {CONFIG_FILENAME}")
        json.dump(continuous_deployment_policy, config_file, indent=4)

    update_continuous_deployment_policy(policy_item_id, policy_etag, CONFIG_FILENAME)
    print("Main function completed")


if __name__ == "__main__":
    main()
