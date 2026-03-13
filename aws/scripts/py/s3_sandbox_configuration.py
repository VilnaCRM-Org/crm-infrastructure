import json
import os


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

    json_string = json.dumps(config, indent=4)

    try:
        with open(output_path, "w") as file:
            file.write(json_string)
    except OSError as e:
        raise RuntimeError(f"Failed to write crm configuration: {e}") from e

    print(f"Config has been written to {output_path}")


def create_s3_policy(
    branch_name: str, project_name: str, output_path: str = "s3_policy.json"
) -> None:
    bucket_name = f"{project_name}-{branch_name}"
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "AWS": "*",
                },
                "Action": "s3:GetObject",
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}/*",
                ],
            },
        ],
    }

    json_string = json.dumps(policy_document, indent=4)

    try:
        with open(output_path, "w") as file:
            file.write(json_string)
    except OSError as e:
        raise RuntimeError(f"Failed to write S3 policy document: {e}") from e

    print(f"Policy has been written to {output_path}")


def main() -> None:
    branch_name = os.environ.get("BRANCH_NAME")
    project_name = os.environ.get("PROJECT_NAME")
    if not branch_name or not project_name:
        raise ValueError(
            f"Missing required env vars: BRANCH_NAME={branch_name}, PROJECT_NAME={project_name}"
        )

    create_crm_configuration()
    create_s3_policy(branch_name=branch_name, project_name=project_name)


if __name__ == "__main__":
    main()
