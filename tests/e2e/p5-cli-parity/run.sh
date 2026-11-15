#!/usr/bin/env bash
# P5 acceptance — `coltman-images generate` as the API's client.
#
# The phase's exit criterion is guard 7's claim: the CLI and a direct POST for
# the same seed produce the same bytes. That is checked with `cmp`, not with a
# similarity score, and the CLI is also checked for the contract it must not
# break: machine output on stdout, diagnostics on stderr, the declared exit
# codes, and no rendering of its own.
#
# Every check prints `CHECK n: ok` or `CHECK n: FAILED <why>`. Nothing is
# retried and nothing is softened.
set -u

ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
EVID="$ROOT/tests/e2e/p5-cli-parity/evidence"
mkdir -p "$EVID"
cd "$ROOT" || exit 1

exec > >(tee "$EVID/transcript.txt") 2>&1

FAILED=0
pass() { echo "CHECK $1: ok${2:+ — $2}"; }
fail() { echo "CHECK $1: FAILED $2"; FAILED=$((FAILED + 1)); }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

PROMPT="parity test"
SEED=5

echo "=== CHECK 1 — generate with no server is refused, and starts nothing ==="
"$ROOT/bin/coltman-images" generate --prompt "x" >"$WORK/noserver.out" 2>"$WORK/noserver.err"
code=$?
echo "exit=$code"; cat "$WORK/noserver.err"
echo "stdout bytes: $(wc -c <"$WORK/noserver.out")"
if [ "$code" -eq 4 ] && [ ! -s "$WORK/noserver.out" ]; then pass 1 "exit 4, nothing on stdout"; else fail 1 "exit=$code"; fi
if [ -e "$ROOT/run/server.json" ]; then fail 1b "a state file appeared; the CLI must never start a server"; else pass 1b "no state file created"; fi

echo
echo "=== start ==="
"$ROOT/bin/coltman-images" start || { echo "cannot start; aborting"; exit 1; }

echo
echo "=== CHECK 2 — a plain generate prints the path and nothing else ==="
cli_out=$("$ROOT/bin/coltman-images" generate --prompt "$PROMPT" --seed "$SEED" --out "$WORK/cli.png" 2>"$WORK/cli.err")
code=$?
echo "exit=$code"; echo "stdout: $cli_out"; echo "stderr bytes: $(wc -c <"$WORK/cli.err")"
if [ "$code" -eq 0 ] && [ "$cli_out" = "$WORK/cli.png" ] && [ ! -s "$WORK/cli.err" ] && [ -s "$WORK/cli.png" ]; then
  pass 2 "stdout is exactly the path, stderr empty, file written"
else
  fail 2 "exit=$code stdout=$cli_out stderr=$(cat "$WORK/cli.err")"
fi
head -c 8 "$WORK/cli.png" | od -An -tx1 | grep -q "89 50 4e 47" && pass 2b "PNG signature" || fail 2b "not a PNG"

echo
echo "=== CHECK 3 — --json prints the whole response object ==="
"$ROOT/bin/coltman-images" generate --prompt "$PROMPT" --seed "$SEED" --out "$WORK/cli2.png" --json >"$WORK/json.out" 2>"$WORK/json.err"
code=$?
python3 - "$WORK/json.out" <<'PY' && pass 3 "response object parsed with every declared field" || fail 3 "unparsable or missing fields"
import json, sys
d = json.load(open(sys.argv[1]))
need = {"out","seed","width","height","model","census","duration_s","render_s","load_s","upscale"}
missing = need - set(d)
print("fields:", sorted(d))
print("missing:", missing or "none")
sys.exit(0 if not missing and d["seed"] == 5 and d["upscale"] is None else 1)
PY
cmp -s "$WORK/cli.png" "$WORK/cli2.png" && pass 3b "same seed, same bytes as CHECK 2" || fail 3b "the same request produced different bytes"

echo
echo "=== CHECK 4 — parity: the CLI and a direct POST for the same seed ==="
curl -s -X POST "127.0.0.1:8420/generate" -H 'Content-Type: application/json' \
  -d "{\"prompt\":\"$PROMPT\",\"seed\":$SEED,\"out\":\"$WORK/api.png\"}" >"$WORK/api.out"
python3 -c "import json,sys; d=json.load(open('$WORK/api.out')); print('api out:', d['out']); sys.exit(0 if d['out'].endswith('api.png') else 1)" \
  && pass 4a "POST wrote its own file" || fail 4a "POST did not write api.png"
if cmp -s "$WORK/cli.png" "$WORK/api.png"; then
  pass 4 "byte-identical: $(sha256sum "$WORK/cli.png" | cut -c1-16) == $(sha256sum "$WORK/api.png" | cut -c1-16)"
else
  fail 4 "CLI and POST differ: $(sha256sum "$WORK/cli.png" | cut -c1-16) vs $(sha256sum "$WORK/api.png" | cut -c1-16)"
fi

echo
echo "=== CHECK 5 — a refused request exits 2, speaks on stderr, writes nothing ==="
"$ROOT/bin/coltman-images" generate --prompt "x" --width 300 --out "$WORK/bad.png" >"$WORK/bad.out" 2>"$WORK/bad.err"
code=$?
echo "exit=$code"; cat "$WORK/bad.err"
if [ "$code" -eq 2 ] && [ ! -s "$WORK/bad.out" ] && [ ! -e "$WORK/bad.png" ]; then
  pass 5 "exit 2, empty stdout, no file"
else
  fail 5 "exit=$code stdout=$(cat "$WORK/bad.out") file=$([ -e "$WORK/bad.png" ] && echo present || echo absent)"
fi

echo
echo "=== CHECK 6 — --upscale reaches the stage, and the file is the size asked for ==="
"$ROOT/bin/coltman-images" generate --prompt "$PROMPT" --seed "$SEED" --width 2560 --height 1440 --upscale --out "$WORK/hd.png" --json >"$WORK/hd.out" 2>"$WORK/hd.err"
code=$?
python3 - "$WORK/hd.out" <<'PY' && pass 6 "2560x1440 declared the stage and its base" || fail 6 "see the printed object"
import json, sys
d = json.load(open(sys.argv[1]))
print("upscale:", d["upscale"])
print("duration_s:", d["duration_s"], "render_s:", d["render_s"])
up = d["upscale"] or {}
ok = (d["width"], d["height"]) == (2560, 1440) and up.get("from") == [1280, 720] and up.get("scale") == 2
sys.exit(0 if ok else 1)
PY
python3 -c "
from PIL import Image; im=Image.open('$WORK/hd.png'); print('file:', im.size)
import sys; sys.exit(0 if im.size==(2560,1440) else 1)" && pass 6b "file is 2560x1440" || fail 6b "wrong file size"

echo
echo "=== stop ==="
"$ROOT/bin/coltman-images" stop || fail stop "stop returned non-zero"
[ -e "$ROOT/run/server.json" ] && fail stop2 "state file survived stop" || pass stop2 "state file gone"
ps -eo args | grep -q "[c]oltman_images.server" && fail stop3 "a server process survived" || pass stop3 "no server process"

echo
echo "=============== failures: $FAILED ==============="
[ "$FAILED" -eq 0 ] && echo "RUN_EXIT=0" && exit 0
echo "RUN_EXIT=1"; exit 1
