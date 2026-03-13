#!/bin/bash

set -e

for candidate in \
    "$CODEBUILD_SRC_DIR"/crm/tests/load/Dockerfile \
    "$CODEBUILD_SRC_DIR"/crm/src/test/load/Dockerfile
do
    if [ -f "$candidate" ]; then
        LOAD_TEST_DOCKERFILE="$candidate"
        break
    fi
done

if [ -z "${LOAD_TEST_DOCKERFILE:-}" ]; then
    echo "Failed to locate CRM load-test Dockerfile." >&2
    exit 1
fi

echo "Normalizing CRM load-test Dockerfile base images: $LOAD_TEST_DOCKERFILE"

sed -i \
    -e 's|^FROM golang:\([^[:space:]]*\)\( AS .*\)\?$|FROM public.ecr.aws/docker/library/golang:\1\2|' \
    -e 's|^FROM golang:\([^[:space:]]*\)\( as .*\)\?$|FROM public.ecr.aws/docker/library/golang:\1\2|' \
    -e 's|^FROM alpine:\([^[:space:]]*\)$|FROM public.ecr.aws/docker/library/alpine:\1|' \
    -e 's|^FROM alpine$|FROM public.ecr.aws/docker/library/alpine:latest|' \
    "$LOAD_TEST_DOCKERFILE"

if grep -Eq '^FROM (golang:|alpine(:|$))' "$LOAD_TEST_DOCKERFILE"; then
    echo "Load-test Dockerfile still references Docker Hub base images after normalization." >&2
    exit 1
fi

echo "Using load-test Dockerfile base images:"
grep '^FROM ' "$LOAD_TEST_DOCKERFILE"
