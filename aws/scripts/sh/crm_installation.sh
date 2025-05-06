#!/bin/bash
echo #### Install Software
n install "${NODEJS_VERSION:?Node.js version is not set}"
n "${NODEJS_VERSION:?Node.js version is not set}"
git clone -b "$CRM_GIT_REPOSITORY_BRANCH" "$CRM_GIT_REPOSITORY_LINK.git" /codebuild-user/crm
cd /codebuild-user/crm/ || {
    echo "Error: Failed to change directory to crm folder" >&2
    exit 1
}
echo #### Install pnpm
npm install -g pnpm || {
    echo "Error: Failed to install pnpm" >&2
    exit 1
}
echo #### Install dependencies
make install || {
    echo "Error: Failed to install dependencies" >&2
    exit 1
}
