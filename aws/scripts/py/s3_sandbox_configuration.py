import json
import os

try:
    ACCOUNT_ID = os.environ["ACCOUNT_ID"]
except KeyError as e:
    raise ValueError(f"Required environment variable {e} is not set") from e


def create_crm_configuration(
    output_path: str = "crm_configuration.json",
) -> None:
    config = {
        "IndexDocument": {
            "Suffix": "index.html",
        },
        "ErrorDocument": {
            "Key": "404.html",
        },
    }

    json_string = json.dumps(config, indent=2)

    try:
        with open(output_path, "w") as file:
            file.write(json_string)
    except OSError as e:
        raise RuntimeError(f"Failed to write crm configuration: {e}") from e

    print(f"Config has been written to {output_path}")


def create_s3_policy(output_path: str = "policy.json") -> None:
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{os.environ['BUCKET_NAME']}/*",
            },
        ],
    }

    json_string = json.dumps(policy_document, indent=2)

    try:
        with open(output_path, "w") as file:
            file.write(json_string)
    except OSError as e:
        raise RuntimeError(f"Failed to write S3 policy document: {e}") from e

    print(f"Policy has been written to {output_path}")


def main() -> None:
    create_crm_configuration()
    create_s3_policy()


if __name__ == "__main__":
    main()
