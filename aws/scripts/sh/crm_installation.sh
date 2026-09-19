#!/bin/bash

set -euo pipefail

echo "#### CRM Installation and Setup"

if [ -n "${CODEBUILD_SRC_DIR_CrmSource:-}" ]; then
    test -f "$CODEBUILD_SRC_DIR_CrmSource/package.json"
    test -n "${CRM_SOURCE_VERSION:-}" || { echo "Missing CRM source revision" >&2; exit 1; }
    mkdir -p "$CODEBUILD_SRC_DIR/crm"
    cp -a "$CODEBUILD_SRC_DIR_CrmSource/." "$CODEBUILD_SRC_DIR/crm/"
else
    # Sandbox builds still select their requested branch explicitly.
    git clone --branch "${CRM_GIT_REPOSITORY_BRANCH:?Missing CRM branch}" \
      "${CRM_GIT_REPOSITORY_LINK:?Missing CRM repository}.git" "$CODEBUILD_SRC_DIR/crm"
    CRM_SOURCE_VERSION=$(git -C "$CODEBUILD_SRC_DIR/crm" rev-parse HEAD)
    export CRM_SOURCE_VERSION
fi
cd "$CODEBUILD_SRC_DIR"/crm/ || {
    echo "Error: Failed to change directory to crm folder" >&2
    exit 1
}

echo "✅ CRM installation completed successfully"
