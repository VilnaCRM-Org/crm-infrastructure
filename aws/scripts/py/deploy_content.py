import json
import hashlib
import mimetypes
import os
import re
import subprocess
from pathlib import Path

BUILD_DIR = os.environ.get("BUILD_DIR", "./out")
DEPLOYMENT_MANIFEST = os.environ.get(
    "DEPLOYMENT_MANIFEST",
    str(Path(os.environ.get("CODEBUILD_SRC_DIR", ".")) / "codepipeline-artifacts/deployment.json"),
)


def cloudfront_staging_enabled():
    return os.environ.get("ENABLE_CLOUDFRONT_STAGING", "").strip().lower() not in {
        "false",
        "0",
        "no",
    }


def get_bucket():
    print("Getting bucket...")
    return os.environ["BUCKET_NAME"]


def get_cloudfront_region():
    cloudfront_region = os.environ.get("CLOUDFRONT_REGION")
    if not cloudfront_region:
        raise RuntimeError(
            "CLOUDFRONT_REGION environment variable is required when CloudFront "
            "staging is enabled"
        )
    return cloudfront_region


def fetch_distributions():
    print("Fetching CloudFront distributions...")
    result = subprocess.check_output(
        [
            "aws",
            "cloudfront",
            "list-distributions",
            "--region",
            get_cloudfront_region(),
            "--no-cli-pager",
        ]
    )
    distributions = json.loads(result.decode())
    print(f"Fetched distributions: {distributions}")
    return distributions


def origin_pair_role(origins, bucket_name):
    """Return a role only for the exact CRM bucket names and regional endpoints."""
    if len(origins) != 2:
        return None

    pairs = {
        "primary": {
            f"{bucket_name}.s3.eu-central-1.amazonaws.com",
            f"{bucket_name}-replication.s3.eu-west-1.amazonaws.com",
        },
        "staging": {
            f"staging.{bucket_name}.s3.eu-central-1.amazonaws.com",
            f"staging.{bucket_name}-replication.s3.eu-west-1.amazonaws.com",
        },
    }
    domains = {origin.get("DomainName", "") for origin in origins}
    for role, pair in pairs.items():
        if domains == pair:
            return role
    return None


def deploy_files(target_bucket):
    print(f"Deploying files to target bucket: {target_bucket}")
    try:
        result = subprocess.check_output(
            [
                "aws", "s3", "sync", BUILD_DIR, f"s3://{target_bucket}",
                "--cache-control", "public,max-age=0,must-revalidate",
            ], text=True
        )
        index_file = Path(BUILD_DIR) / "index.html"
        subprocess.check_output(
            [
                "aws", "s3", "cp", str(index_file), f"s3://{target_bucket}/index.html",
                "--cache-control", "public,max-age=0,must-revalidate",
                "--content-type", "text/html; charset=utf-8",
            ],
            text=True,
        )
        # Only explicitly content-hashed build files are safe to cache as immutable.
        build_root = Path(BUILD_DIR)
        hashed_name = re.compile(r"\.[0-9a-fA-F]{8,}\.")
        for path in build_root.rglob("*"):
            if not path.is_file() or not hashed_name.search(path.name):
                continue
            relative_path = path.relative_to(build_root).as_posix()
            content_type, _ = mimetypes.guess_type(path.name)
            command = [
                "aws", "s3", "cp", str(path), f"s3://{target_bucket}/{relative_path}",
                "--cache-control", "public,max-age=31536000,immutable",
            ]
            if content_type:
                command.extend(["--content-type", content_type])
            subprocess.check_output(command, text=True)
        print(f"Successfully deployed to bucket: {target_bucket}")
        print(f"Deploy output: {result}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error deploying to bucket {target_bucket}: {e}")
        print(f"Command output: {e.output}")
        print(f"Return code: {e.returncode}")
        raise


def find_project_distributions(bucket_name):
    """
    Find the specific distributions for this project based on bucket name.
    Filters out distributions from other projects like vilnacrm.com.
    """
    print(f"Finding distributions for project with bucket: {bucket_name}")

    cloudfront_distributions = fetch_distributions()
    project_distributions = {"production": None, "staging": None}
    matches = {"production": [], "staging": []}

    for dist in cloudfront_distributions["DistributionList"]["Items"]:
        aliases = dist.get("Aliases", {}).get("Items", [])
        origins = dist.get("Origins", {}).get("Items", [])

        aliases_match = bucket_name in aliases or f"www.{bucket_name}" in aliases
        staging = bool(dist.get("Staging", False))
        if origin_pair_role(origins, bucket_name) is None:
            print(f"Skipping distribution {dist['Id']} - origins are not an exact CRM bucket pair")
            continue
        if staging or aliases_match:
            role = "staging" if staging else "production"
        else:
            print(f"Skipping distribution {dist['Id']} - not for project {bucket_name}")
            continue
        matches[role].append(dist)

    for role, distributions in matches.items():
        if len(distributions) > 1:
            raise ValueError(
                f"Expected exactly one CRM {role} distribution for {bucket_name}; "
                f"found {[item['Id'] for item in distributions]}"
            )
        if distributions:
            project_distributions[role] = distributions[0]

    return project_distributions


def determine_deployment_target(bucket_name):
    """
    Determine which bucket to deploy to based on current production setup.
    Deploy to the environment that is NOT currently serving production traffic.
    Only considers distributions for this specific project.
    """
    print("Determining deployment target for blue-green deployment...")

    if not cloudfront_staging_enabled():
        print(
            "CloudFront staging is disabled, deploying directly to the production bucket"
        )
        return bucket_name

    project_distributions = find_project_distributions(bucket_name)

    production_distribution = project_distributions["production"]
    staging_distribution = project_distributions["staging"]

    if not production_distribution:
        print(f"ERROR: Could not find production distribution for {bucket_name}")
        print("This might happen if:")
        print("1. The distribution aliases don't match the bucket name")
        print("2. The distribution origins don't point to the expected buckets")
        print("3. Multiple projects exist and filtering failed")
        raise ValueError(f"No production distribution found for {bucket_name}")

    if not staging_distribution:
        raise ValueError(f"No staging distribution found for {bucket_name}")

    # Check which bucket production is currently pointing to
    origins = production_distribution["Origins"]["Items"]
    production_role = origin_pair_role(origins, bucket_name)
    if production_role is None:
        raise ValueError(
            f"Production distribution {production_distribution['Id']} must have "
            "the exact CRM base and replication origin pair"
        )
    staging_role = origin_pair_role(
        staging_distribution["Origins"]["Items"], bucket_name
    )
    if staging_role is None or staging_role == production_role:
        raise ValueError(
            "Primary and staging distributions must point to opposite exact CRM "
            "base/replication bucket pairs"
        )

    print(
        f"Production distribution {production_distribution['Id']} points to: "
        f"the {production_role} bucket pair"
    )

    if production_role == "staging":
        # Production is on Green (staging bucket), deploy to Blue (main bucket)
        target_bucket = bucket_name
        environment = "Blue"
        print("Production is currently on Green, deploying to Blue")
    else:
        # Production is on Blue (main bucket), deploy to Green (staging bucket)
        target_bucket = f"staging.{bucket_name}"
        environment = "Green"
        print("Production is currently on Blue, deploying to Green")

    print(f"Deploying to {environment} environment: {target_bucket}")
    return target_bucket


def main():
    print("Starting blue-green deployment...")
    bucket_name = get_bucket()
    print(f"Base bucket name: {bucket_name}")

    # Determine which environment to deploy to (the non-production one)
    target_bucket = determine_deployment_target(bucket_name)

    distributions = None
    if cloudfront_staging_enabled():
        distributions = find_project_distributions(bucket_name)
        if not distributions["production"] or not distributions["staging"]:
            raise ValueError("Both CRM primary and staging distributions are required")
    source_revision = os.environ.get("CRM_SOURCE_VERSION", "").strip()
    if not source_revision:
        raise RuntimeError(
            "CRM_SOURCE_VERSION is required to identify the built CRM source"
        )
    manifest = {
        "target_bucket": target_bucket,
        "crm_source_revision": source_revision,
        "index_sha256": hashlib.sha256(
            (Path(BUILD_DIR) / "index.html").read_bytes()
        ).hexdigest(),
    }
    if distributions is not None:
        manifest["origins"] = {
            "primary": distributions["staging"]["Origins"],
            "staging": distributions["production"]["Origins"],
        }
    # Deploy to the target environment only
    deploy_files(target_bucket)
    Path(DEPLOYMENT_MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    Path(DEPLOYMENT_MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Blue-green deployment completed. New version deployed to: {target_bucket}")
    print("Use the release pipeline to promote this version to production.")

    print("Main function completed.")


if __name__ == "__main__":
    main()
