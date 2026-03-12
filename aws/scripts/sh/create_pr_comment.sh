#!/bin/bash

# Description:
#   This script creates a pull request comment with a link to the latest version of the project
#   when run in the context of a pull request.
#
# Inputs:
#   - IS_PULL_REQUEST: An environment variable indicating whether the script is running in the context of a pull request.
#   - PR_NUMBER: An environment variable containing the pull request number.
#   - GITHUB_REPOSITORY: An environment variable containing the GitHub repository name.
#   - PROJECT_NAME: An environment variable containing the project name.
#   - BRANCH_NAME: An environment variable containing the branch name.
#   - AWS_DEFAULT_REGION: An environment variable containing the AWS region.
#
# Security:
#   - Requires GitHub token with PR comment permissions
#   - Token is retrieved securely from AWS Secrets Manager
#
# Error Handling:
#   - Validates all required environment variables
#   - Handles GitHub authentication failures
#   - Handles comment creation failures

# Validate required environment variables
for var in IS_PULL_REQUEST GITHUB_REPOSITORY PROJECT_NAME BRANCH_NAME AWS_DEFAULT_REGION CODEBUILD_SRC_DIR SCRIPT_DIR; do
    if [ -z "${!var}" ]; then
        echo "Error: $var environment variable is not set"
        exit 1
    fi
done

# Check if the script is running in the context of a pull request
if [ "$IS_PULL_REQUEST" != "1" ]; then
    echo "Not a pull request. Skipping comment creation."
    exit 0
fi

if [ -z "${PR_NUMBER}" ] || [ "${PR_NUMBER}" = "null" ]; then
    echo "PR number is unavailable. Skipping comment creation."
    exit 0
fi

# Set up a cleanup action to log out of GitHub after the script completes
trap 'gh auth logout >/dev/null 2>&1 || true' EXIT

echo "Running in the context of a pull request."

# Authenticate with GitHub using the token retrieved directly from AWS Secrets Manager
echo "Authenticating with GitHub..."

# shellcheck source=aws/scripts/sh/gh_auth_login.sh
if ! . "${CODEBUILD_SRC_DIR}/${SCRIPT_DIR}/sh/gh_auth_login.sh"; then
    echo "GitHub authentication failed."
    exit 1
fi

echo "Authentication successful."

# Create a pull request comment with a link to the latest version of the project
echo "Creating pull request comment..."
COMMENT_BODY="Latest Version is ready: http://$PROJECT_NAME-$BRANCH_NAME.s3-website.$AWS_DEFAULT_REGION.amazonaws.com
This deployed crm will be automatically deleted after 7 days.
To keep it active, please make a new commit to trigger a redeployment."

if ! gh pr comment "$PR_NUMBER" -R "$GITHUB_REPOSITORY" --body "$COMMENT_BODY"; then
    echo "Failed to create the pull request comment. Please check the provided environment variables."
    exit 1
else
    echo "Successfully created a comment on PR #$PR_NUMBER with the latest version link."
fi

echo "Pull request comment created successfully."
