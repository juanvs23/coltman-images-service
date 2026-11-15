#!/usr/bin/env bash
# P4 acceptance — one pass over the seven checks the phase declares.
#
# This is the run whose transcript is the phase's exit evidence: start, a second
# start, one generate, one refusal, two concurrent generates, stop, and the
# absent `generate` subcommand. It also probes two lifecycle edges the protocol
# declares but the seven checks do not reach: a stale state file, and `stop`
# against a state file whose pid is gone.
#
# Every check prints `CHECK n: ok` or `CHECK n: FAILED <why>`. Nothing is
# retried and nothing is softened: a red line here is a red line in the report.
#
# Values cross from JSON into the shell only as file paths or as bare integers;
# a JSON string is never re-parsed by the shell (a quoted path is not a path).
set -u

ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
EVID="$ROOT/tests/e2e/p4-acceptance/evidence"
mkdir -p "$EVID"
cd "$ROOT" || exit 1

exec > >(tee "$EVID/transcript.txt") 2>&1

FAILED=0
pass() { echo "CHECK $1: ok${2:+ — $2}"; }
fail() { echo "CHECK $1: FAILED — $2"; FAILED=$((FAILED + 1)); }

# The pids whose argv is `python -u -m coltman_images.server …`. The NUL separators
# make this structural: a shell command line that merely mentions the module cannot
# match it.
server_pids() {
  python3 - <<'PY'
import pathlib
pids = []
for entry in pathlib.Path("/proc").iterdir():
    if not entry.name.isdigit():
        continue
    try:
        argv = (entry / "cmdline").read_bytes()
    except OSError:
        continue
    if b"\x00-m\x00coltman_images.server\x00" in argv:
        pids.append(int(entry.name))
print(" ".join(str(pid) for pid in sorted(pids)))
PY
}

state_pid() { python3 -c 'import json; print(json.load(open("run/server.json"))["pid"])'; }

echo "=============== P4 acceptance — $(date -u +%Y-%m-%dT%H:%M:%SZ) ==============="
echo

# --- 1: start ---------------------------------------------------------------
echo "=== CHECK 1 — start, /health, state file ==="
./bin/coltman-images start
CODE=$?
echo "exit=$CODE"
[ "$CODE" -eq 0 ] || fail 1 "start exited $CODE"

curl -s --max-time 5 -o "$EVID/health.json" -w 'health http=%{http_code}\n' "http://127.0.0.1:8420/health"
echo "health: $(cat "$EVID/health.json")"
echo "state file: $ROOT/run/server.json"
cat run/server.json
echo "pids matching '-m coltman_images.server': $(server_pids)"

python3 - "$EVID/health.json" "run/server.json" "$(server_pids)" <<'PY'
import json
import pathlib
import sys

health = json.loads(pathlib.Path(sys.argv[1]).read_text())
state = json.loads(pathlib.Path(sys.argv[2]).read_text())
pids = sys.argv[3].split()
problems = []
if health.get("status") != "warm":
    problems.append(f"status is {health.get('status')!r}")
expected_census = {"float8": 239, "plain": 282, "other": 0, "total": 521}
if state.get("census") != expected_census:
    problems.append(f"state census is {state.get('census')!r}")
if health.get("census") != expected_census:
    problems.append(f"health census is {health.get('census')!r}")
if health.get("queue") != {"depth": 0}:
    problems.append(f"queue is {health.get('queue')!r}")
for key in ("pid", "port", "model", "started_at", "warm_at", "census"):
    if key not in state:
        problems.append(f"server.json is missing {key}")
    elif health.get(key) != state.get(key):
        problems.append(f"/health {key}={health.get(key)!r} but server.json says {state.get(key)!r}")
if pids != [str(state.get("pid"))]:
    problems.append(f"server pids {pids} != state pid {state.get('pid')}")
print("CHECK 1: ok" if not problems else "CHECK 1: FAILED — " + "; ".join(problems))
sys.exit(0 if not problems else 1)
PY
[ $? -eq 0 ] || FAILED=$((FAILED + 1))
echo

# --- 2: second start --------------------------------------------------------
echo "=== CHECK 2 — a second start is idempotent ==="
PID_BEFORE=$(state_pid)
./bin/coltman-images start
CODE=$?
echo "exit=$CODE"
PID_AFTER=$(state_pid)
PIDS=$(server_pids)
echo "pid before=$PID_BEFORE pid after=$PID_AFTER pids=[$PIDS]"
if [ "$CODE" -eq 0 ] && [ "$PID_BEFORE" = "$PID_AFTER" ] && [ "$PIDS" = "$PID_AFTER" ]; then
  pass 2 "same pid $PID_AFTER, one process"
else
  fail 2 "exit=$CODE, pids=[$PIDS], state pid=$PID_AFTER"
fi
echo "-- second start with a differing --port --"
./bin/coltman-images start --port 9999
echo "exit=$?  pids=[$(server_pids)]"
[ "$(server_pids)" = "$PID_AFTER" ] || fail 2 "a second process appeared"
echo

# --- 3: generate ------------------------------------------------------------
echo "=== CHECK 3 — POST /generate (1280x720, seed 7) ==="
nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -lms 200 > "$EVID/vram-during-generate.txt" &
POLLER=$!
START=$(date +%s.%N)
curl -s -o "$EVID/generate.json" -w 'http=%{http_code}\n' \
  -X POST http://127.0.0.1:8420/generate -d '{"prompt":"a lighthouse at dusk","seed":7}'
END=$(date +%s.%N)
kill "$POLLER" 2>/dev/null
wait "$POLLER" 2>/dev/null
echo "wall $(python3 -c "print(f'{$END - $START:.2f} s')")"
cat "$EVID/generate.json"; echo
python3 - "$EVID/generate.json" <<'PY'
import json
import pathlib
import sys

body = json.loads(pathlib.Path(sys.argv[1]).read_text())
problems = []
for key in ("out", "seed", "width", "height", "duration_s", "render_s", "upscale"):
    if key not in body:
        problems.append(f"{key} is missing from the response")
if body.get("seed") != 7:
    problems.append(f"seed is {body.get('seed')!r}")
if (body.get("width"), body.get("height")) != (1280, 720):
    problems.append(f"size is {body.get('width')}x{body.get('height')}")
if body.get("upscale") is not None:
    problems.append(f"upscale is {body.get('upscale')!r}, expected null")
path = pathlib.Path(body.get("out", ""))
print(f"out={path}")
if not path.is_absolute():
    problems.append(f"{path} is not absolute")
elif not path.is_file():
    problems.append(f"{path} does not exist")
else:
    blob = path.read_bytes()
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        problems.append(f"{path} is not a PNG")
    if len(blob) < 1024:
        problems.append(f"{path} is {len(blob)} bytes")
    print(f"file: {len(blob)} bytes, PNG signature ok")
print("CHECK 3: ok" if not problems else "CHECK 3: FAILED — " + "; ".join(problems))
sys.exit(0 if not problems else 1)
PY
[ $? -eq 0 ] || FAILED=$((FAILED + 1))
echo "-- vram sampled during the request (MiB) --"
echo "max=$(sort -n "$EVID/vram-during-generate.txt" | tail -1) min=$(sort -n "$EVID/vram-during-generate.txt" | head -1) total=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits)"
echo

# --- 4: refusal -------------------------------------------------------------
echo "=== CHECK 4 — an unknown field is refused before the queue ==="
LOG_BEFORE=$(grep -c 'served:' run/server.log || true)
curl -s -o "$EVID/refusal.json" -w 'http=%{http_code}\n' \
  -X POST http://127.0.0.1:8420/generate -d '{"prompt":"x","bogus":1}'
cat "$EVID/refusal.json"; echo
DEPTH=$(curl -s http://127.0.0.1:8420/health | python3 -c 'import json,sys; print(json.load(sys.stdin)["queue"]["depth"])')
sleep 2
LOG_AFTER=$(grep -c 'served:' run/server.log || true)
echo "queue depth=$DEPTH renders before=$LOG_BEFORE after=$LOG_AFTER"
python3 - "$EVID/refusal.json" "$LOG_BEFORE" "$LOG_AFTER" <<'PY'
import json
import pathlib
import sys

body = json.loads(pathlib.Path(sys.argv[1]).read_text())
before, after = int(sys.argv[2]), int(sys.argv[3])
problems = []
if body.get("error", {}).get("code") != "invalid_request":
    problems.append(f"body is {body!r}")
if before != after:
    problems.append(f"the render count moved from {before} to {after}")
print("CHECK 4: ok" if not problems else "CHECK 4: FAILED — " + "; ".join(problems))
sys.exit(0 if not problems else 1)
PY
[ $? -eq 0 ] || FAILED=$((FAILED + 1))
echo "-- the other refusals, for the record --"
for BODY in '{}' '{"prompt":""}' '{"prompt":"x","width":1001}' '{"prompt":"x","out":"relative.png"}' \
            '{"prompt":"x","width":4000,"height":4000,"upscale":true}' 'not json'; do
  printf '%s -> ' "$BODY"
  curl -s -X POST http://127.0.0.1:8420/generate -d "$BODY" -w ' [%{http_code}]\n'
done
echo

# --- 5: two concurrent generates -------------------------------------------
echo "=== CHECK 5 — two concurrent generates, one worker ==="
curl -s -o "$EVID/concurrent-a.json" -w 'A http=%{http_code}\n' \
  -X POST http://127.0.0.1:8420/generate -d '{"prompt":"a lighthouse at dusk","seed":11}' &
A_JOB=$!
curl -s -o "$EVID/concurrent-b.json" -w 'B http=%{http_code}\n' \
  -X POST http://127.0.0.1:8420/generate -d '{"prompt":"a lighthouse at dusk","seed":12}' &
B_JOB=$!
sleep 2
echo "-- /health while both are accepted (depth is the waiting count) --"
for _ in 1 2 3 4 5; do
  curl -s http://127.0.0.1:8420/health | python3 -c 'import json,sys; h=json.load(sys.stdin); print("depth", h["queue"]["depth"])'
  sleep 1
done
wait "$A_JOB" "$B_JOB"
echo "-- responses --"
for F in "$EVID/concurrent-a.json" "$EVID/concurrent-b.json"; do
  echo "$(basename "$F"): $(cat "$F")"
done
python3 - "$EVID/concurrent-a.json" "$EVID/concurrent-b.json" <<'PY'
import json
import pathlib
import sys

a, b = (json.loads(pathlib.Path(p).read_text()) for p in sys.argv[1:3])
problems = []
for name, body in (("A", a), ("B", b)):
    if "error" in body:
        problems.append(f"{name} failed: {body['error']}")
    elif not pathlib.Path(body.get("out", "")).is_file():
        problems.append(f"{name} wrote no file")
if "duration_s" in a and "duration_s" in b:
    short, long = sorted((a["duration_s"], b["duration_s"]))
    # The queued request must have waited for the other one, not shared the GPU.
    if long < short * 1.5:
        problems.append(f"duration_s {short} and {long} do not show a serialised wait")
    else:
        print(f"serialised: {short:.3f} s then {long:.3f} s (the queued request waited "
              f"{long - short:.3f} s for the one ahead of it)")
print("CHECK 5: ok" if not problems else "CHECK 5: FAILED — " + "; ".join(problems))
sys.exit(0 if not problems else 1)
PY
[ $? -eq 0 ] || FAILED=$((FAILED + 1))
echo

# --- 6: stop ---------------------------------------------------------------
echo "=== CHECK 6 — stop releases the card ==="
PID=$(state_pid)
echo "vram before stop: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
time ./bin/coltman-images stop
CODE=$?
echo "exit=$CODE"
[ "$CODE" -eq 0 ] || fail 6 "stop exited $CODE"
curl -s -o /dev/null -w 'health after stop: http=%{http_code}\n' --max-time 3 http://127.0.0.1:8420/health \
  || echo "health after stop: no answer (curl $?)"
if [ -e run/server.json ]; then fail 6 "run/server.json still exists"; else echo "run/server.json: gone"; fi
echo "pids matching '-m coltman_images.server': [$(server_pids)]"
if [ -n "$(server_pids)" ]; then fail 6 "a server process survived stop"; fi
echo "vram after stop: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
echo "-- a second stop is a no-op --"
./bin/coltman-images stop
CODE2=$?
echo "exit=$CODE2"
[ "$CODE2" -eq 0 ] || fail 6 "the second stop exited $CODE2"
echo

# --- 7: generate is absent --------------------------------------------------
echo "=== CHECK 7 — 'generate' does not exist yet ==="
./bin/coltman-images generate --prompt "x"
CODE=$?
echo "exit=$CODE"
[ "$CODE" -ne 0 ] && pass 7 "refused with exit $CODE" || fail 7 "generate exited 0"
echo

# --- edges the protocol declares -------------------------------------------
echo "=== EXTRA — a stale state file is diagnosed, never auto-started from ==="
printf '{"pid": 999999, "port": 8420, "model": "z-image-turbo-fp8", "started_at": "x", "warm_at": "x", "census": {}}\n' > run/server.json
./bin/coltman-images start
CODE=$?
echo "exit=$CODE  state file now: $([ -e run/server.json ] && echo present || echo gone)  pids=[$(server_pids)]"
[ "$CODE" -eq 4 ] && [ ! -e run/server.json ] && [ -z "$(server_pids)" ] \
  && echo "EXTRA: ok — diagnosed, cleared, nothing started" \
  || { echo "EXTRA: FAILED"; FAILED=$((FAILED + 1)); }
echo

echo "=== EXTRA — stop with a state file whose pid is gone ==="
printf '{"pid": 999999, "port": 8420, "model": "z-image-turbo-fp8", "started_at": "x", "warm_at": "x", "census": {}}\n' > run/server.json
./bin/coltman-images stop
CODE=$?
echo "exit=$CODE  state file: $([ -e run/server.json ] && echo present || echo gone)"
[ "$CODE" -eq 0 ] && [ ! -e run/server.json ] && echo "EXTRA: ok" || { echo "EXTRA: FAILED"; FAILED=$((FAILED + 1)); }
echo

cp run/server.log "$EVID/server.log" 2>/dev/null || true
echo "=============== failures: $FAILED ==============="
exit "$FAILED"
