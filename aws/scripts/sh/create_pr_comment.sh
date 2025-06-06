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
for var in IS_PULL_REQUEST PR_NUMBER GITHUB_REPOSITORY PROJECT_NAME BRANCH_NAME AWS_DEFAULT_REGION; do
    if [ -z "${!var}" ]; then
        echo "Error: $var environment variable is not set"
        exit 1
    fi
done

# Set up a cleanup action to log out of GitHub after the script completes
trap 'gh auth logout' EXIT

# Check if the script is running in the context of a pull request
if [ "$IS_PULL_REQUEST" -eq 1 ]; then

    echo "Running in the context of a pull request."

    # Authenticate with GitHub using the token retrieved directly from AWS Secrets Manager
    echo "Authenticating with GitHub..."

    SECRET_ID=$(aws secretsmanager list-secrets --query "SecretList[?starts_with(Name, 'crm-github-token-') && DeletedDate==null].Name" --output text)
    if [ -z "$SECRET_ID" ]; then
        echo "Error: No active GitHub token secret found."
        exit 1
    fi

    if ! aws secretsmanager get-secret-value \
        --secret-id "$SECRET_ID" \
        --query 'SecretString' \
        --output text | jq -r '.token' | gh auth login --with-token; then
        echo "GitHub authentication failed. Please ensure the secret contains a valid JSON object with a 'token' field."
        exit 1
    fi

    echo "Authentication successful."

    # Create a pull request comment with a link to the latest version of the project
    echo "Creating pull request comment..."
    COMMENT_BODY="Latest Version is ready: http://$PROJECT_NAME-$BRANCH_NAME.s3-crm.$AWS_DEFAULT_REGION.amazonaws.com 
    This deployed crm will be automatically deleted after 7 days.
    To keep it active, please make a new commit to trigger a redeployment."
    
    if ! gh pr comment "$PR_NUMBER" -R "$GITHUB_REPOSITORY" --body "$COMMENT_BODY"; then
        echo "Failed to create the pull request comment. Please check the provided environment variables."
        exit 1
    else
        echo "Successfully created a comment on PR #$PR_NUMBER with the latest version link."
    fi

    echo "Pull request comment created successfully."

else
    echo "Not a pull request. Skipping comment creation."
fi