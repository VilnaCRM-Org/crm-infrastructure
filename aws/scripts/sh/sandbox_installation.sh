#!/bin/bash
echo #### Install Software

# Validate required environment variables
: "${CRM_GIT_REPOSITORY_LINK:?Repository link is not set}"
: "${BRANCH_NAME:?Branch name is not set}"

if [ "${IS_PULL_REQUEST:-0}" = "1" ]; then
    CRM_GIT_REPOSITORY_BRANCH="$BRANCH_NAME"
else
    CRM_GIT_REPOSITORY_BRANCH="${CRM_GIT_REPOSITORY_BRANCH:-main}"
fi

git clone -b "$CRM_GIT_REPOSITORY_BRANCH" "$CRM_GIT_REPOSITORY_LINK.git" /codebuild-user/crm || {
    echo "Error: Failed to clone repository" >&2
    exit 1
}

cd /codebuild-user/crm/ || exit 1
