#!/bin/bash

# Install k6 using the official binary release
echo "Installing k6 binary..."
apk add --no-cache curl tar || {
    echo "Failed to install curl and tar" >&2
    exit 1
}

# Download and install k6 binary
K6_VERSION="v0.49.0"
echo "Downloading k6 ${K6_VERSION}..."
curl -L "https://github.com/grafana/k6/releases/download/${K6_VERSION}/k6-${K6_VERSION}-linux-amd64.tar.gz" -o k6.tar.gz || {
    echo "Failed to download k6" >&2
    exit 1
}

echo "Extracting k6..."
tar -xzf k6.tar.gz || {
    echo "Failed to extract k6" >&2
    exit 1
}

echo "Installing k6..."
mv "k6-${K6_VERSION}-linux-amd64/k6" /usr/local/bin/ || {
    echo "Failed to move k6 binary" >&2
    exit 1
}

# Clean up
rm -rf k6.tar.gz "k6-${K6_VERSION}-linux-amd64"

# Verify installation
k6 version || {
    echo "Failed to verify k6 installation" >&2
    exit 1
}

escape_sed_replacement() {
    printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g'
}

assert_config_contains() {
    expected_value="$1"
    if ! grep -Fq "$expected_value" "$LOAD_TEST_DIR"/config.json; then
        echo "Config rewrite failed: expected value not found -> $expected_value" >&2
        exit 1
    fi
}

assert_config_not_contains() {
    unexpected_value="$1"
    if grep -Fq "$unexpected_value" "$LOAD_TEST_DIR"/config.json; then
        echo "Config rewrite failed: placeholder still present -> $unexpected_value" >&2
        exit 1
    fi
}

if [ -d "$CODEBUILD_SRC_DIR"/crm/tests/load ]; then
    LOAD_TEST_DIR="$CODEBUILD_SRC_DIR"/crm/tests/load
elif [ -d "$CODEBUILD_SRC_DIR"/crm/src/test/load ]; then
    LOAD_TEST_DIR="$CODEBUILD_SRC_DIR"/crm/src/test/load
else
    echo "Failed to locate CRM load test directory" >&2
    exit 1
fi

# Configure load test settings
echo "Configuring load test settings..."
if [ ! -f "$LOAD_TEST_DIR"/config.json.dist ]; then
    echo "Missing load-test template: $LOAD_TEST_DIR/config.json.dist" >&2
    exit 1
fi

cp "$LOAD_TEST_DIR"/config.json.dist "$LOAD_TEST_DIR"/config.json || {
    echo "Failed to create $LOAD_TEST_DIR/config.json" >&2
    exit 1
}

# Check if we're in DinD mode and configure accordingly.
# In the CRM test compose file, the service hostname is `prod`, so keep that
# default unless a different explicit DinD host is provided.
# Force DinD mode detection for docker:dind image
if docker info 2>/dev/null | grep -q "docker:dind" || [ "${DIND:-0}" = "1" ]; then
    echo "Configuring for DinD mode - using container networking"
    # For DinD mode, use the Docker Compose service hostname and HTTP protocol.
    dind_host="${CRM_DIND_LOAD_TEST_HOST:-prod}"
    escaped_dind_host=$(escape_sed_replacement "${dind_host}")

    sed -i "s|\"host\": \"prod\"|\"host\": \"${escaped_dind_host}\"|" "$LOAD_TEST_DIR"/config.json
    if [ "$dind_host" != "prod" ]; then
        assert_config_not_contains '"host": "prod"'
    fi
    assert_config_contains "\"host\": \"${dind_host}\""
    echo "✅ DinD mode: Keeping HTTP protocol and using container hostname '${dind_host}'"
else
    echo "Configuring for production deployment"
    if [ -z "${CRM_URL:-}" ] || [ -z "${CLOUDFRONT_HEADER:-}" ]; then
        echo "CRM_URL and CLOUDFRONT_HEADER must be set for production load-test config" >&2
        exit 1
    fi

    # For production deployment, use external URLs
    escaped_crm_url=$(escape_sed_replacement "${CRM_URL}")
    escaped_cloudfront_header=$(escape_sed_replacement "${CLOUDFRONT_HEADER}")

    sed -i "s/http/https/" "$LOAD_TEST_DIR"/config.json
    sed -i "s|localhost|${escaped_crm_url}|g" "$LOAD_TEST_DIR"/config.json
    sed -i "s/3000/443/" "$LOAD_TEST_DIR"/config.json
    sed -i "s|Continuous-Deployment-Header-Name|aws-cf-cd-${escaped_cloudfront_header}|g" "$LOAD_TEST_DIR"/config.json
    sed -i "s|continuous-deployment-header-value|${escaped_cloudfront_header}|g" "$LOAD_TEST_DIR"/config.json

    assert_config_not_contains '"protocol": "http"'
    assert_config_not_contains 'localhost'
    assert_config_not_contains '"port": "3000"'
    assert_config_not_contains 'Continuous-Deployment-Header-Name'
    assert_config_not_contains 'continuous-deployment-header-value'
    assert_config_contains '"protocol": "https"'
    assert_config_contains "\"host\": \"${CRM_URL}\""
    assert_config_contains '"port": "443"'
    assert_config_contains "aws-cf-cd-${CLOUDFRONT_HEADER}"
    assert_config_contains "${CLOUDFRONT_HEADER}"
fi

echo "k6 installation completed successfully!"
