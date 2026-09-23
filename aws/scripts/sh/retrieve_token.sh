#!/bin/bash
# This file is sourced by CodeBuild; never trace credential assignments.
set +x
set -euo pipefail

if [ -z "${AWS_DEFAULT_REGION:-}" ]; then
  echo "Error: AWS_DEFAULT_REGION is not set."
  exit 1
fi

# Each CLI process has a hard limit as well as socket limits. The caller's
# deadline includes both calls, parsing, and sleeps; SDK retries are disabled.
_github_token_aws() {
  local remaining=$((token_deadline - SECONDS))
  local limit=30
  if ((remaining <= 0)); then
    return 1
  fi
  if ((remaining < limit)); then
    limit=$remaining
  fi
  AWS_MAX_ATTEMPTS=1 AWS_RETRY_MODE=standard AWS_PAGER="" \
    timeout --signal=KILL "${limit}s" aws "$@" \
      --cli-connect-timeout "$limit" --cli-read-timeout "$limit" 2>/dev/null
}

_github_token_load() {
  local wait_seconds=${GITHUB_TOKEN_WAIT_SECONDS-0}
  local min_ttl=${GITHUB_TOKEN_MIN_TTL_SECONDS-0}
  local poll_seconds=${GITHUB_TOKEN_POLL_SECONDS-15}
  local value token_deadline freshness_enabled=0 remaining delay now
  local SECRET_ID SECRET_VALUE candidate EXPIRY EXPIRY_EPOCH

  # Reject signs, fractions, leading zeroes, and oversized arithmetic inputs.
  for value in "$wait_seconds" "$min_ttl" "$poll_seconds"; do
    if [[ ! $value =~ ^(0|[1-9][0-9]{0,3})$ ]]; then
      echo "Error: Invalid GitHub token freshness limits."
      return 1
    fi
  done
  if ((wait_seconds > 3600 || min_ttl > 3600 || poll_seconds < 1 || poll_seconds > 300)); then
    echo "Error: Invalid GitHub token freshness limits."
    return 1
  fi
  if ((wait_seconds > 0 || min_ttl > 0)); then
    freshness_enabled=1
  fi
  # No-wait mode still bounds its single retrieval (two CLI calls, 30s each).
  token_deadline=$((SECONDS + (wait_seconds > 0 ? wait_seconds : 60)))
  unset GITHUB_TOKEN
  echo "Retrieving and using GitHub token for authentication..."

  while :; do
    if ((SECONDS >= token_deadline)); then
      echo "Error: Timed out waiting for a fresh GitHub token."
      return 1
    fi
    # Reselect on each poll in case rotation selected a newly created secret.
    if ! SECRET_ID=$(_github_token_aws secretsmanager list-secrets --query "sort_by(SecretList[?starts_with(Name, 'crm-github-token-') && DeletedDate==null], &CreatedDate)[-1].Name" --output text); then
      echo "Error: GitHub token secret lookup failed or exceeded its time limit."
      return 1
    fi
    if [[ -z $SECRET_ID || $SECRET_ID == "None" ]]; then
      echo "Error: No active GitHub token secret found."
      return 1
    fi
    if ! SECRET_VALUE=$(_github_token_aws secretsmanager get-secret-value --secret-id "$SECRET_ID" --query 'SecretString' --output text); then
      echo "Error: GitHub token secret retrieval failed or exceeded its time limit."
      return 1
    fi
    if ! candidate=$(printf '%s' "$SECRET_VALUE" | jq -ers \
      'if length == 1 and (.[0] | type == "object") then .[0].token else null end
       | strings | select(length > 0 and (test("[[:space:][:cntrl:]]") | not))' 2>/dev/null); then
      echo "Error: GitHub token must be a nonempty string without whitespace or control characters."
      return 1
    fi
    if ! EXPIRY=$(printf '%s' "$SECRET_VALUE" | jq -er \
      'if .expires_at == null then "" else .expires_at | strings end
       | select(test("[[:space:][:cntrl:]]") | not)' 2>/dev/null); then
      echo "Error: Invalid GitHub token expiration time."
      return 1
    fi
    if [[ -z $EXPIRY ]]; then
      if ((freshness_enabled)); then
        echo "Error: GitHub token expiration time is required for freshness checks."
        return 1
      fi
    else
      if ! EXPIRY_EPOCH=$(python3 -c '
from datetime import datetime
import re, sys
value = sys.stdin.read().strip()
if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
    sys.exit(1)
print(int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()))
' <<< "$EXPIRY" 2>/dev/null); then
        echo "Error: Invalid GitHub token expiration time."
        return 1
      fi
    fi
    now=$(date -u +%s)
    if ((SECONDS >= token_deadline)); then
      echo "Error: Timed out waiting for a fresh GitHub token."
      return 1
    fi
    if [[ -z $EXPIRY ]] || ((EXPIRY_EPOCH > now && EXPIRY_EPOCH - now >= min_ttl)); then
      export GITHUB_TOKEN="$candidate"
      echo "GitHub token retrieved successfully."
      return 0
    fi
    if ((wait_seconds == 0)); then
      echo "Error: GitHub token has expired or has insufficient remaining lifetime."
      return 1
    fi
    remaining=$((token_deadline - SECONDS))
    delay=$poll_seconds
    if ((remaining < delay)); then
      delay=$remaining
    fi
    if ((delay > 0)); then
      sleep "$delay"
    fi
  done
}

_github_token_load
unset -f _github_token_load _github_token_aws
