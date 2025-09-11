#!/bin/bash

# CRM Installation Script
# Handles git repository cloning and pnpm installation

set -e

echo "#### CRM Installation and Setup"

# Clean up existing directory if it exists
if [ -d "$CODEBUILD_SRC_DIR/crm" ]; then
    echo "Cleaning up existing crm directory..."
    rm -rf "$CODEBUILD_SRC_DIR/crm"
fi

# Clone the CRM repository
mkdir -p "$CODEBUILD_SRC_DIR"/crm
git clone -b "$CRM_GIT_REPOSITORY_BRANCH" "$CRM_GIT_REPOSITORY_LINK.git" "$CODEBUILD_SRC_DIR"/crm
cd "$CODEBUILD_SRC_DIR"/crm/ || {
    echo "Error: Failed to change directory to crm folder" >&2
    exit 1
}

echo "#### Installing pnpm"
npm install -g pnpm || {
    echo "Error: Failed to install pnpm" >&2
    exit 1
}

echo "✅ CRM installation completed successfully"
