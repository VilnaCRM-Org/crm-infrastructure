#!/bin/bash
# Never trace credentials, even if the caller enables shell tracing.
set +x
set -euo pipefail

# Check required environment variables
: "${VILNACRM_APP_ID:?Need to set VILNACRM_APP_ID}"
: "${VILNACRM_APP_PRIVATE_KEY:?Need to set VILNACRM_APP_PRIVATE_KEY}"

echo "Generating new GitHub token..."

# Authenticate as a GitHub App
jwt=$(python3 -c "
import jwt, time, os
print(jwt.encode(
    {
        'iat': int(time.time()),
        'exp': int(time.time()) + 600,
        'iss': os.getenv('VILNACRM_APP_ID')
    }, 
    os.getenv('VILNACRM_APP_PRIVATE_KEY').replace('\\n', '\n'), 
    algorithm='RS256'
))
")

# Get installation ID
response=$(curl --fail --silent --show-error --max-time 30 --retry 2 \
  -H "Authorization: Bearer $jwt" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/app/installations)

installation_id=$(echo "$response" | jq -r '.[0].id')

if [ -z "$installation_id" ] || [ "$installation_id" = "null" ]; then
  echo "Failed to retrieve installation ID"
  exit 1
fi

# Create an installation access token
token_response=$(curl --fail --silent --show-error --max-time 30 --retry 2 -X POST \
  -H "Authorization: Bearer $jwt" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/app/installations/$installation_id/access_tokens")

NEW_TOKEN=$(echo "$token_response" | jq -r '.token')
TOKEN_EXPIRATION=$(echo "$token_response" | jq -r '.expires_at')

if [ -z "$NEW_TOKEN" ] || [ "$NEW_TOKEN" = "null" ]; then
  echo "Failed to generate new token"
  exit 1
fi

if [ -z "$TOKEN_EXPIRATION" ] || [ "$TOKEN_EXPIRATION" = "null" ]; then
  echo "Failed to retrieve token expiration time"
  exit 1
fi

# A successful API response must still leave enough time for a downstream plan.
if ! expiration_epoch=$(date -u -d "$TOKEN_EXPIRATION" +%s 2>/dev/null); then
  echo "Invalid GitHub token expiration time"
  exit 1
fi
if (( expiration_epoch - $(date -u +%s) < 2700 )); then
  echo "GitHub token has less than 45 minutes of validity"
  exit 1
fi

# Create a JSON object with the token and expiration time
if ! SECRET_JSON=$(jq -n --arg token "$NEW_TOKEN" --arg expires_at "$TOKEN_EXPIRATION" \
  '{token: $token, expires_at: $expires_at}'); then
  echo "Error: Generated JSON is missing required fields"
  exit 1
fi

# Select the same newest active secret as retrieve_token.sh.
# JSON evaluates the selector after all Secrets Manager pages aggregate.
if ! SECRET_ID=$(aws secretsmanager list-secrets \
  --region "${AWS_REGION}" \
  --query "sort_by(SecretList[?starts_with(Name, 'crm-github-token-') && DeletedDate==null], &CreatedDate)[-1].Name" \
  --output json | jq -ers 'if length == 1 and (.[0] | type == "string") and (.[0] | length > 0) then .[0] else empty end'); then
  echo "No active secret found with prefix 'crm-github-token-'"
  exit 1
fi

echo "✅ Found secret: ${SECRET_ID}"

# Store the new JSON in AWS Secrets Manager
if ! aws secretsmanager put-secret-value \
  --region "${AWS_REGION}" \
  --secret-id "${SECRET_ID}" \
  --secret-string "${SECRET_JSON}"; then
  echo "Error: Failed to update secret in AWS Secrets Manager"
  exit 1
fi

echo "GitHub token has been rotated and updated in AWS Secrets Manager."
