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
# Each invoke carries a nonce that the record echoes back, which is what tells
# this load's result from another run's — an Event invoke returns a status and
# no request id, so there is nothing else to correlate on. A record that does
# not match is left where it is, for its own waiter to collect.
#
# Reads FIXTURE from the environment: empty loads everything, which is what a
# deploy does.
set -euo pipefail

FUNCTION="${FUNCTION:-openforge-catalog-fixtures}"
QUEUE="${QUEUE:-${FUNCTION}-result}"
# Above the function's own ceiling plus the event's maximum age, so a load
# that genuinely runs out of time reports its own timeout rather than being
# cut off here. Both callers allow 20 minutes, which is above this.
DEADLINE_SECONDS="${DEADLINE_SECONDS:-1080}"

# Echoed back in the record's requestPayload, which is the only way to tell
# this load's result from another run's: an Event invoke returns a status and
# no request id, so there is nothing else to correlate on.
NONCE=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')

queue_url=$(aws sqs get-queue-url --queue-name "$QUEUE" --output text --query QueueUrl)

if [ -n "${FIXTURE:-}" ]; then
  # Built with json.dumps rather than string interpolation so a name
  # containing a quote cannot malform the payload.
  payload=$(FIXTURE="$FIXTURE" NONCE="$NONCE" python3 -c \
    'import json, os; print(json.dumps({"fixture": os.environ["FIXTURE"], "nonce": os.environ["NONCE"]}))')
  echo "loading one fixture: $FIXTURE"
else
  payload=$(NONCE="$NONCE" python3 -c \
    'import json, os; print(json.dumps({"nonce": os.environ["NONCE"]}))')
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
found=""
while [ "$(date +%s)" -lt "$deadline" ]; do
  # A failed receive is not a failed load. Tolerated rather than fatal,
  # because aborting here would reintroduce the fragility this script exists
  # to remove, with one chance per poll instead of one for the whole load.
  # The sleep stands in for the long poll a failed call never paid for;
  # without it the loop re-polls at process-startup speed until the deadline.
  if ! aws sqs receive-message --queue-url "$queue_url" --wait-time-seconds 20 \
    --max-number-of-messages 1 --output json > result.json; then
    echo "  receive failed; retrying"
    sleep 20
    continue
  fi

  if ! grep -q ReceiptHandle result.json 2>/dev/null; then
    echo "  still loading"
    continue
  fi

  # Another run's record. Left alone rather than deleted, so its visibility
  # timeout returns it to whoever is waiting for it.
  if ! NONCE="$NONCE" python3 -c '
import json, os, sys
m = json.load(open("result.json"))["Messages"][0]
record = json.loads(m["Body"])
sent = (record.get("requestPayload") or {}).get("nonce")
sys.exit(0 if sent == os.environ["NONCE"] else 1)
'; then
    echo "  a record from another run; leaving it"
    continue
  fi

  found=yes
  break
done

if [ -z "$found" ]; then
  echo "no result after ${DEADLINE_SECONDS}s; the load may still be running" >&2
  echo "check /aws/lambda/${FUNCTION} before re-running, because a second" >&2
  echo "load would be queued behind the one concurrency slot and, if it" >&2
  echo "cannot start in time, reports itself as expired" >&2
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

# Lambda says why it delivered this record, and it is the only field that
# distinguishes "the handler ran and returned" from "the event never ran". A
# handler that raised arrives as RetriesExhausted, an expiry as
# EventAgeExceeded, and neither carries a payload worth reading — so there is
# no separate functionError check, because a function error cannot reach here
# with a Success condition.
condition = record.get("requestContext", {}).get("condition")
if condition != "Success":
    sys.exit(f"fixture load failed ({condition}); see the record above")

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
