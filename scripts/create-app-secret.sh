#!/usr/bin/env bash
# create-app-secret.sh — create the openforge-catalog/<env>/app secret once per account.
#
# Generates a fresh API_TOKEN and SECRET_KEY and copies the Cloudflare R2 credentials
# from a source Lambda's environment (staging and production share one R2 bucket).
# Nothing secret is printed; verify with the printed key names and lengths only.
#
#   ./scripts/create-app-secret.sh production production staging   # <env> <aws-profile> <source-profile>

set -euo pipefail

ENVIRONMENT="${1:?usage: $0 <staging|production> <aws-profile> <source-profile>}"
PROFILE="${2:?aws profile for the target account}"
SOURCE_PROFILE="${3:?aws profile of the account whose Lambda holds the R2 credentials}"
SOURCE_FUNCTION="Openforge-Catalog-API"
SECRET_NAME="openforge-catalog/${ENVIRONMENT}/app"

if aws secretsmanager describe-secret --profile "$PROFILE" --secret-id "$SECRET_NAME" >/dev/null 2>&1; then
  echo "$SECRET_NAME already exists in profile $PROFILE; delete it deliberately before re-creating" >&2
  exit 1
fi

# Read the source env once, keep it in a variable, never echo it.
SOURCE_ENV=$(aws lambda get-function-configuration --profile "$SOURCE_PROFILE" \
  --function-name "$SOURCE_FUNCTION" --query 'Environment.Variables' --output json)

SECRET_JSON=$(python3 - "$SOURCE_ENV" <<'PY'
import json, secrets, sys
src = json.loads(sys.argv[1])
out = {
    "API_TOKEN": secrets.token_urlsafe(32),
    "SECRET_KEY": secrets.token_urlsafe(48),
}
for k in ("CLOUDFLARE_ENDPOINT", "CLOUDFLARE_ACCESS_KEY_ID", "CLOUDFLARE_SECRET_ACCESS_KEY"):
    if not src.get(k):
        sys.exit(f"source Lambda has no {k}")
    out[k] = src[k]
print(json.dumps(out))
PY
)

aws secretsmanager create-secret --profile "$PROFILE" --name "$SECRET_NAME" \
  --description "openforge-catalog ${ENVIRONMENT} runtime secrets (read by terraform/environments/${ENVIRONMENT})" \
  --secret-string "$SECRET_JSON" --query ARN --output text

# Verification without disclosure: key names and value lengths.
python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print({k: len(v) for k, v in d.items()})' "$SECRET_JSON"
