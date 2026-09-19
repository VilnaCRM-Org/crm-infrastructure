#!/bin/bash
set -euo pipefail

if [ -z "${AWS_DEFAULT_REGION:-}" ]; then
  echo "Error: AWS_DEFAULT_REGION is not set."
  exit 1
fi

echo "Retrieving and using GitHub token for authentication..."
SECRET_ID=$(aws secretsmanager list-secrets --query "sort_by(SecretList[?starts_with(Name, 'crm-github-token-') && DeletedDate==null], &CreatedDate)[-1].Name" --output text)
if [ -z "$SECRET_ID" ] || [ "$SECRET_ID" = "None" ]; then
  echo "Error: No active GitHub token secret found."
  exit 1
fi
# Retrieve secret value once and parse both token and expiry
SECRET_VALUE=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --query 'SecretString' --output text)
if ! GITHUB_TOKEN=$(printf '%s' "$SECRET_VALUE" | jq -er \
  '.token | strings | select(length > 0 and (test("[[:space:][:cntrl:]]") | not))' 2>/dev/null); then
  echo "Error: GitHub token must be a nonempty string without whitespace or control characters."
  exit 1
fi
EXPIRY=$(echo "$SECRET_VALUE" | jq -r '.expires_at // empty')
if [[ -n "$EXPIRY" ]]; then
  EXPIRY_EPOCH=$(python3 -c 'from datetime import datetime; import sys; print(int(datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00")).timestamp()))' "$EXPIRY")
  if [[ "$(date -u +%s)" -gt "$EXPIRY_EPOCH" ]]; then
    echo "Error: GitHub token has expired."
    exit 1
  fi
fi
export GITHUB_TOKEN
echo "GitHub token retrieved successfully."
