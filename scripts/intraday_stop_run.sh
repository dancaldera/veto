#!/bin/bash
# Fill-derived 8% poll stop + reconcile. Alpaca PAPER only (fake money).
# Skips flatten when a collar put is live. Invoked every 30 minutes.
#
# DRY_RUN=1 bash scripts/intraday_stop_run.sh
set -u

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR" || exit 1
# shellcheck source=scripts/_lib.sh
source "$REPO_DIR/scripts/_lib.sh"

LOG="$REPO_DIR/results/stop_monitor.log"
rotate_log "$LOG"
VETO="$(veto_bin "$REPO_DIR")"
EXTRA=""
[ "${DRY_RUN:-0}" = "1" ] && EXTRA="--dry-run"

{
  echo "--------------------------------------------------------------------"
  echo "Veto stops: $(date -u +"%Y-%m-%dT%H:%M:%SZ")  dry_run=${DRY_RUN:-0}"

  OUT="$("$VETO" stops $EXTRA 2>&1)"
  stop_rc=$?
  if [ "${DRY_RUN:-0}" = "1" ]; then
    RECON_OUT="dry run — reconciliation skipped"
    reconcile_rc=0
  else
    RECON_OUT="$("$VETO" reconcile 2>&1)"
    reconcile_rc=$?
  fi
  printf '%s\n\n%s\n' "$OUT" "$RECON_OUT"
  rc=$stop_rc
  [ "$reconcile_rc" -ne 0 ] && rc=$reconcile_rc
  echo "Exit code: $rc"

  if [ "$rc" -ne 0 ]; then
    notify "Veto" "Stop monitor FAILED (exit $rc) — results/stop_monitor.log"
  else
    heartbeat "$REPO_DIR/results/.last_success_stopmonitor"
  fi
} >> "$LOG" 2>&1
exit "$rc"
