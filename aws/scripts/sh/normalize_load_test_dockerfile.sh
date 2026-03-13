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
    -E \
    -e 's|^([Ff][Rr][Oo][Mm][[:space:]]+)(--platform=[^[:space:]]+[[:space:]]+)?(docker\.io/library/)?golang:([^[:space:]]+)([[:space:]]+[Aa][Ss][[:space:]]+[^[:space:]]+)?$|\1\2public.ecr.aws/docker/library/golang:\4\5|' \
    -e 's|^([Ff][Rr][Oo][Mm][[:space:]]+)(--platform=[^[:space:]]+[[:space:]]+)?(docker\.io/library/)?alpine:([^[:space:]]+)([[:space:]]+[Aa][Ss][[:space:]]+[^[:space:]]+)?$|\1\2public.ecr.aws/docker/library/alpine:\4\5|' \
    -e 's|^([Ff][Rr][Oo][Mm][[:space:]]+)(--platform=[^[:space:]]+[[:space:]]+)?(docker\.io/library/)?alpine([[:space:]]+[Aa][Ss][[:space:]]+[^[:space:]]+)?$|\1\2public.ecr.aws/docker/library/alpine:latest\4|' \
    "$LOAD_TEST_DOCKERFILE"

if offending_refs=$(grep -Ei '^[Ff][Rr][Oo][Mm][[:space:]]+(--platform=[^[:space:]]+[[:space:]]+)?(docker\.io/library/)?(golang:|alpine([:[:space:]]|$))' "$LOAD_TEST_DOCKERFILE"); then
    echo "Load-test Dockerfile still references Docker Hub base images after normalization:" >&2
    echo "$offending_refs" >&2
    exit 1
fi

echo "Using load-test Dockerfile base images:"
grep '^FROM ' "$LOAD_TEST_DOCKERFILE"
