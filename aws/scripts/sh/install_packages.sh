#!/bin/sh

# Package Installation Script
# POSIX bootstrap: the Alpine DinD image does not include Bash yet.

set -e

echo "#### Installing Required Packages"

# Install required packages using apk
apk add --no-cache \
    bash \
    git \
    curl \
    nodejs \
    npm \
    make \
    sed \
    docker-cli \
    docker-compose \
    || {
        echo "Error: Failed to install required packages" >&2
        exit 1
    }

echo "✅ All required packages installed successfully"
