#!/bin/bash
# Shared helpers for Veto paper-loop wrappers. Paper account only (fake money).

rotate_log() {
  local log="$1"
  mkdir -p "$(dirname "$log")"
  if [ -f "$log" ]; then
    local lines
    lines="$(wc -l < "$log" | tr -d ' ')"
    if [ "${lines:-0}" -gt 1000 ]; then
      tail -n 400 "$log" > "${log}.tmp"
      mv "${log}.tmp" "$log"
    fi
  fi
}

notify() {
  local title="$1"
  local body="$2"
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "$title" "$body" || true
  fi
}

heartbeat() {
  date +%s > "$1"
}

veto_bin() {
  local repo="$1"
  if [ -x "$repo/.venv/bin/veto" ]; then
    echo "$repo/.venv/bin/veto"
  else
    echo "veto"
  fi
}
