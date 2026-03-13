#!/bin/bash

# terraform_installation.sh
#
# Purpose: Sets up infrastructure management tools for Terraform/Terraspace builds
# Context: Part of the CI/CD pipelines for deploying CRM infrastructure
# Requirements:
#   - AWS CodeBuild environment
#   - Ruby for Terraform testing
#   - RPM package manager

echo "## Install Terraform"
TERRAFORM_VERSION="${TERRAFORM_VERSION:-1.14.3}"
TFENV_DIR="${HOME}/.tfenv"
PROFILE_FILE="${HOME}/.bash_profile"

if [ -d "$TFENV_DIR" ]; then
    if ! git -C "$TFENV_DIR" pull --ff-only; then
        echo "Failed to update tfenv repository"
        exit 1
    fi
else
    if ! git clone --depth=1 https://github.com/tfutils/tfenv.git "$TFENV_DIR"; then
        echo "Failed to clone tfenv repository"
        exit 1
    fi
fi

if ! grep -q '\.tfenv/bin' "$PROFILE_FILE" 2>/dev/null; then
    if ! echo 'export PATH="$HOME/.tfenv/bin:$PATH"' >>"$PROFILE_FILE"; then
        echo "Failed to update PATH in .bash_profile"
        exit 1
    fi
fi
export PATH="$TFENV_DIR/bin:$PATH"

tfenv install "${TERRAFORM_VERSION}" || { echo "Failed to install Terraform ${TERRAFORM_VERSION}"; exit 1; }
tfenv use "${TERRAFORM_VERSION}" || { echo "Failed to switch to Terraform ${TERRAFORM_VERSION}"; exit 1; }

GEMFILE_PATH="${CODEBUILD_SRC_DIR}/terraform/Gemfile"
if [ ! -f "$GEMFILE_PATH" ]; then
    echo "Gemfile not found at: $GEMFILE_PATH"
    exit 1
fi

if [ ! -f "${GEMFILE_PATH}.lock" ]; then
    echo "Warning: Gemfile.lock not found. This may lead to inconsistent dependencies."
fi

echo "Installing Ruby dependencies..."
if ! bundle install --gemfile "$GEMFILE_PATH"; then
    echo "Failed to install Ruby dependencies!"
    exit 1
fi
