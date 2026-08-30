#!/usr/bin/env bash
set -Eeuo pipefail

port="${PORT:-10000}"
api_pid=""
agent_pid=""
shutting_down=0

stop_children() {
  local exit_code="${1:-0}"
  shutting_down=1
  trap - SIGINT SIGTERM

  if [[ -n "$api_pid" ]] && kill -0 "$api_pid" 2>/dev/null; then
    kill -TERM "$api_pid"
  fi
  if [[ -n "$agent_pid" ]] && kill -0 "$agent_pid" 2>/dev/null; then
    kill -TERM "$agent_pid"
  fi

  wait "$api_pid" 2>/dev/null || true
  wait "$agent_pid" 2>/dev/null || true
  exit "$exit_code"
}

on_signal() {
  stop_children 0
}

trap on_signal SIGINT SIGTERM

python main.py start --log-level=info &
agent_pid=$!

uvicorn beacon_call.api:app --host 0.0.0.0 --port "$port" --workers 1 &
api_pid=$!

set +e
wait -n "$agent_pid" "$api_pid"
child_status=$?
set -e

if ((shutting_down == 0)); then
  echo "A required BeaconCall process exited unexpectedly; stopping the service." >&2
  if ((child_status == 0)); then
    child_status=1
  fi
fi
stop_children "$child_status"
