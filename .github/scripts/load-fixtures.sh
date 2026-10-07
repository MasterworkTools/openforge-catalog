#!/usr/bin/env bash
# Invoke the fixtures function and decide whether the load succeeded.
#
# One copy, used by both deploy workflows and the manual re-run, because the
# decision is the subtle part: `aws lambda invoke` exits 0 for a function that
# raised, so the invoke metadata has to be read or a failed load passes as a
# success. Three inlined copies of that check is three chances to get it wrong
# in only two of them.
#
# Reads FIXTURE from the environment: empty loads everything, which is what a
# deploy does.
set -euo pipefail

FUNCTION="${FUNCTION:-openforge-catalog-fixtures}"

if [ -n "${FIXTURE:-}" ]; then
  # Built with json.dumps rather than string interpolation so a name
  # containing a quote cannot malform the payload.
  payload=$(FIXTURE="$FIXTURE" python3 -c \
    'import json, os; print(json.dumps({"fixture": os.environ["FIXTURE"]}))')
  echo "loading one fixture: $FIXTURE"
else
  payload='{}'
  echo "loading every fixture"
fi

# --cli-read-timeout 0: botocore's default read timeout is 60 s, well under the
# function's 900 s budget, so a long load would fail the deploy it had actually
# completed — and the retry would then land on a function with reserved
# concurrency 1 and throttle.
aws lambda invoke --function-name "$FUNCTION" \
  --cli-read-timeout 0 \
  --cli-binary-format raw-in-base64-out --payload "$payload" \
  response.json > invoke.json

echo "--- invoke metadata"; cat invoke.json; echo
echo "--- payload";         cat response.json; echo

# A throttle is different from a raise: reserved concurrency is 1, so a second
# invoke is rejected outright and the CLI exits non-zero above rather than
# reaching this.
python3 - <<'PY'
import json, sys

meta = json.load(open("invoke.json"))
if meta.get("FunctionError"):
    sys.exit(f"fixture load failed ({meta['FunctionError']}); see the payload above")

payload = json.load(open("response.json"))
if payload.get("ok") is not True:
    sys.exit(f"fixture load did not report ok: {payload}")

if payload["blueprints_changed"]:
    print(f"loaded {payload['files']} fixtures; blueprints changed in:")
    for entry in payload["applied"]:
        print(f"  {entry['file']}: {entry}")
else:
    print(f"loaded {payload['files']} fixtures; no blueprint changes")
PY
