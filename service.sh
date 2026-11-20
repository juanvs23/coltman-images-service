#!/usr/bin/env bash
# service.sh — operator control for the coltman-images service.
#
# This is a convenience wrapper around bin/coltman-images (the CLI, protocol
# section 5). It declares no command of the system: `start`, `generate` and
# `stop` are the CLI's own and are passed through untouched. `restart`, `status`
# and `logs` are operator conveniences over the CLI, run/server.json,
# /health and run/server.log — reads and wrappers, never a second implementation.
#
# It does not chdir, so relative --out and --image paths keep the meaning a
# shell gives them (the CLI resolves them against the operator's directory).

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CLI="$ROOT/bin/coltman-images"
PYTHON="$ROOT/.venv/bin/python"
LOG_FILE="$ROOT/run/server.log"

die() {
  printf 'service.sh: %s\n' "$*" >&2
  exit 1
}

require_cli() {
  [[ -x "$CLI" ]] || die "the CLI is missing or not executable: $CLI"
}

require_python() {
  [[ -x "$PYTHON" ]] || die "the project interpreter is missing: $PYTHON"
}

usage() {
  cat <<EOF
usage: ./service.sh <command> [arguments]

Operator control for the coltman-images service. The CLI (bin/coltman-images)
owns the three commands of the system; this script passes them through and adds
operator reads on top of run/server.json, /health and run/server.log.

commands:
  start [CLI options]    start the server and wait until warm (CLI: start)
  stop                   drain and shut down (CLI: stop)
  restart [CLI options]  stop, then start with those options
  status [--json]        what the state file, /health and the lock actually say
  logs [-f] [LINES]      tail run/server.log; -f follows, LINES defaults to 50
  generate [CLI options] render one still through the running server (CLI: generate)
  help                   this text

examples:
  ./service.sh start --model moss-dmd-int8
  ./service.sh start --ui
  ./service.sh status
  ./service.sh generate --prompt "a lighthouse at dusk" --seed 7
  ./service.sh logs -f

status exits 0 when a server answers, 1 when none does (stopped or stale state),
2 when a process owns the card but the port is silent (warming up), and 3 when
run/server.json cannot be read. Use restart to clear a stale state file.
EOF
}

cmd_status() {
  require_python
  "$PYTHON" - "$ROOT" "$@" <<'PY'
import fcntl
import json
import pathlib
import sys
import urllib.error
import urllib.request

root = pathlib.Path(sys.argv[1])
as_json = "--json" in sys.argv[2:]

state_file = root / "run" / "server.json"
lock_file = root / "run" / "server.lock"
log_file = root / "run" / "server.log"

state = None
state_error = None
try:
    state = json.loads(state_file.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError("it is not a JSON object")
except FileNotFoundError:
    pass
except (OSError, ValueError) as exc:
    state = None
    state_error = str(exc)

port = state.get("port") if isinstance(state, dict) else None
health = None
if isinstance(port, int):
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health", timeout=2.0
        ) as response:
            body = json.loads(response.read())
            health = body if isinstance(body, dict) else None
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        health = None

# The lock is the truth (protocol section 6): the state file is a convenience.
lock_held = False
lock_holder = None
try:
    with lock_file.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            handle.seek(0)
            text = handle.read().strip()
            lock_held = True
            lock_holder = int(text) if text.isdigit() else None
except FileNotFoundError:
    pass

if health is not None and health.get("status") == "warm":
    outcome = "running"
elif lock_held:
    outcome = "owned"
elif state_error is not None:
    outcome = "unreadable"
elif state is not None:
    outcome = "stale"
else:
    outcome = "stopped"

codes = {"running": 0, "stopped": 1, "stale": 1, "owned": 2, "unreadable": 3}

if as_json:
    print(
        json.dumps(
            {
                "outcome": outcome,
                "state": state,
                "health": health,
                "lock": {"held": lock_held, "holder": lock_holder},
                "log": str(log_file),
            },
            indent=2,
        )
    )
    raise SystemExit(codes[outcome])


def show(label: str, value: object) -> None:
    print(f"  {label:<9} {value}")


def census_line(census: object) -> str:
    if not isinstance(census, dict) or not census:
        return "not reported"
    return " ".join(f"{key}={value}" for key, value in census.items())


if outcome == "running":
    pid = health.get("pid", state.get("pid") if isinstance(state, dict) else None)
    bound = health.get("port", port)
    print("service: running")
    show("pid", pid)
    show("port", bound)
    show("model", health.get("model", "not reported"))
    show("state", health.get("status", "not reported"))
    show("started", health.get("started_at", "not reported"))
    show("warm", health.get("warm_at", "not reported"))
    queue = health.get("queue")
    show("queue", queue.get("depth") if isinstance(queue, dict) else "not reported")
    show("census", census_line(health.get("census")))
    show("api", f"http://127.0.0.1:{bound}")
    show("log", log_file)
elif outcome == "owned":
    print("service: not answering yet — a process owns the card")
    show("pid", lock_holder if lock_holder is not None else "unknown (run/server.lock)")
    show("port", port if port is not None else "not known until it binds")
    show("hint", "a server that took the lock is warming up; `./service.sh stop` can reach it")
elif outcome == "stale":
    pid = state.get("pid", "unknown")
    print("service: not running — run/server.json is stale")
    show("pid", pid)
    show("port", port if port is not None else "unknown")
    show("hint", "run `./service.sh restart` to clear it and start again")
elif outcome == "unreadable":
    print("service: run/server.json cannot be read")
    show("error", state_error)
    show("hint", "run `./service.sh restart` to clear it and start again")
else:
    print("service: not running")

raise SystemExit(codes[outcome])
PY
}

cmd_logs() {
  local follow=0
  local lines=50

  while (($#)); do
    case "$1" in
      -f|--follow)
        follow=1
        ;;
      *)
        if [[ "$1" =~ ^[0-9]+$ ]]; then
          lines="$1"
        else
          die "logs: unknown argument '$1' (usage: ./service.sh logs [-f] [LINES])"
        fi
        ;;
    esac
    shift
  done

  [[ -f "$LOG_FILE" ]] || die "no log yet at $LOG_FILE — start the service first"
  if ((follow)); then
    tail -n "$lines" -f "$LOG_FILE"
  else
    tail -n "$lines" "$LOG_FILE"
  fi
}

cmd_restart() {
  require_cli
  "$CLI" stop
  "$CLI" start "$@"
}

main() {
  local command="${1:-help}"
  if (($#)); then
    shift
  fi

  case "$command" in
    start)
      require_cli
      exec "$CLI" start "$@"
      ;;
    stop)
      require_cli
      exec "$CLI" stop
      ;;
    generate)
      require_cli
      exec "$CLI" generate "$@"
      ;;
    restart)
      cmd_restart "$@"
      ;;
    status)
      cmd_status "$@"
      ;;
    logs)
      cmd_logs "$@"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      die "unknown command '$command' — ./service.sh help"
      ;;
  esac
}

main "$@"
