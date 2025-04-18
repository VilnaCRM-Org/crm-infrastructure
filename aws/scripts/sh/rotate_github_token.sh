#!/bin/bash
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
response=$(curl -s \
  -H "Authorization: Bearer $jwt" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/app/installations)

installation_id=$(echo "$response" | jq -r '.[0].id')

if [ -z "$installation_id" ] || [ "$installation_id" = "null" ]; then
  echo "Failed to retrieve installation ID"
  exit 1
fi

# Create an installation access token
token_response=$(curl -s -X POST \
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

# Create a JSON object with the token and expiration time
if ! SECRET_JSON=$(jq -n --arg token "$NEW_TOKEN" --arg expires_at "$TOKEN_EXPIRATION" \
  '{token: $token, expires_at: $expires_at}'); then
  echo "Error: Generated JSON is missing required fields"
  exit 1
fi

# Search for an active secret
SECRET_ID=$(aws secretsmanager list-secrets \
  --region "${AWS_REGION}" \
  --query "SecretList[?starts_with(Name, 'crm-github-token-') && DeletionDate==null].Name | [0]" \
  --output text)

if [ -z "$SECRET_ID" ] || [ "$SECRET_ID" = "None" ]; then
  echo "No active secret found with prefix 'crm-github-token-"
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
