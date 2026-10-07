#!/usr/bin/env bash
# Invoke the fixtures function and decide whether the load succeeded.
#
# One copy, used by both deploy workflows and the manual re-run, because the
# decision is the subtle part and three inlined copies of it is three chances
# to get it wrong in only two of them.
#
# The invoke is asynchronous. A load runs for minutes, and a synchronous call
# makes the deploy depend on one socket surviving all of it: a dropped
# connection fails a job whose load was still working, and the CLI's retry
# then starts a second invoke that the reserved concurrency of 1 rejects — so
# the job fails on a throttle and the real attempt's result is discarded.
#
# Instead Lambda delivers the outcome to an SQS queue, configured as the
# function's on-success and on-failure destination. The record carries the
# handler's own return value, so this still gates on what the handler decided.
#
# Reads FIXTURE from the environment: empty loads everything, which is what a
# deploy does.
set -euo pipefail

FUNCTION="${FUNCTION:-openforge-catalog-fixtures}"
QUEUE="${QUEUE:-${FUNCTION}-result}"
# Above the function's own 900 s ceiling, so a load that genuinely runs out of
# time reports its own timeout rather than being cut off here.
DEADLINE_SECONDS="${DEADLINE_SECONDS:-1080}"

queue_url=$(aws sqs get-queue-url --queue-name "$QUEUE" --output text --query QueueUrl)

# Drain by receiving rather than purging: purge-queue is rate limited to once a
# minute and takes effect asynchronously, so it cannot be relied on to have
# finished before the invoke. A stale record here would otherwise be read as
# this load's result.
while true; do
  stale=$(aws sqs receive-message --queue-url "$queue_url" \
    --max-number-of-messages 10 --output json)
  handles=$(printf '%s' "$stale" | python3 -c \
    'import json,sys; d=sys.stdin.read().strip(); print("\n".join(m["ReceiptHandle"] for m in (json.loads(d).get("Messages") or [])) if d else "")')
  [ -z "$handles" ] && break
  echo "discarding a stale result record"
  while IFS= read -r handle; do
    aws sqs delete-message --queue-url "$queue_url" --receipt-handle "$handle"
  done <<< "$handles"
done

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

aws lambda invoke --function-name "$FUNCTION" \
  --invocation-type Event \
  --cli-binary-format raw-in-base64-out --payload "$payload" \
  /dev/null > invoke.json

echo "--- invoke ack"; cat invoke.json; echo

python3 - <<'PY'
import json, sys

ack = json.load(open("invoke.json"))
# An Event invoke is accepted with 202. Anything else never reached Lambda,
# and no record will ever arrive on the queue.
if ack.get("StatusCode") != 202:
    sys.exit(f"the fixtures function was not accepted for invocation: {ack}")
PY

echo "waiting for the load to report"
deadline=$(( $(date +%s) + DEADLINE_SECONDS ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  # Long polling, so this is a handful of calls over a load's lifetime rather
  # than a busy loop.
  aws sqs receive-message --queue-url "$queue_url" --wait-time-seconds 20 \
    --max-number-of-messages 1 --output json > result.json
  if [ -s result.json ] && grep -q ReceiptHandle result.json; then
    break
  fi
  echo "  still loading"
done

if ! grep -q ReceiptHandle result.json 2>/dev/null; then
  echo "no result after ${DEADLINE_SECONDS}s; the load may still be running" >&2
  echo "check /aws/lambda/${FUNCTION} before re-running, because a second" >&2
  echo "load would be rejected while the first holds the concurrency slot" >&2
  exit 1
fi

handle=$(python3 -c \
  'import json; print(json.load(open("result.json"))["Messages"][0]["ReceiptHandle"])')
aws sqs delete-message --queue-url "$queue_url" --receipt-handle "$handle"

python3 - <<'PY'
import json, sys

record = json.loads(json.load(open("result.json"))["Messages"][0]["Body"])
print("--- result record")
print(json.dumps({k: v for k, v in record.items() if k != "requestPayload"}, indent=2))

# Lambda says why it delivered this record. Anything but Success means the
# handler raised, or the event expired without ever running — which is what a
# collision with a manual load looks like.
condition = record.get("requestContext", {}).get("condition")
if condition != "Success":
    sys.exit(f"fixture load failed ({condition}); see the record above")

if record.get("responseContext", {}).get("functionError"):
    sys.exit("fixture load failed; see the record above")

payload = record.get("responsePayload") or {}
if payload.get("ok") is not True:
    sys.exit(f"fixture load did not report ok: {payload}")

if payload["blueprints_changed"]:
    print(f"loaded {payload['files']} fixtures; blueprints changed in:")
    for entry in payload["applied"]:
        print(f"  {entry['file']}: {entry}")
else:
    print(f"loaded {payload['files']} fixtures; no blueprint changes")
PY
