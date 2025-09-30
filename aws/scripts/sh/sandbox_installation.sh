#!/bin/bash

# Validate required environment variables
: "${CRM_GIT_REPOSITORY_LINK:?Repository link is not set}"
: "${BRANCH_NAME:?Branch name is not set}"

git clone -b "$BRANCH_NAME" "$CRM_GIT_REPOSITORY_LINK.git" /codebuild-user/crm || {
    echo "Error: Failed to clone repository" >&2
    exit 1
}

cd /codebuild-user/crm/ || exit 1

echo #### Install dependencies
make install || { echo "Error: Failed to install dependencies" >&2; exit 1; }
