#!/bin/bash
# Gap-capped stock intents after the US cash open. Alpaca PAPER only (fake money).
# Invoked weekdays at 09:31 America/New_York by veto-stockexecution.timer.
#
# DRY_RUN=1 bash scripts/execute_stock_intents.sh
set -u

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR" || exit 1
# shellcheck source=scripts/_lib.sh
source "$REPO_DIR/scripts/_lib.sh"

LOG="$REPO_DIR/results/stock_execution.log"
rotate_log "$LOG"
VETO="$(veto_bin "$REPO_DIR")"
EXTRA=""
[ "${DRY_RUN:-0}" = "1" ] && EXTRA="--dry-run"

{
  echo "--------------------------------------------------------------------"
  echo "Veto stock execution: $(date -u +"%Y-%m-%dT%H:%M:%SZ")  dry_run=${DRY_RUN:-0}"

  OUT="$("$VETO" execute --asset stock $EXTRA 2>&1)"
  exec_rc=$?
  if [ "${DRY_RUN:-0}" = "1" ]; then
    RECON_OUT="dry run — reconciliation skipped"
    reconcile_rc=0
  else
    RECON_OUT="$("$VETO" reconcile 2>&1)"
    reconcile_rc=$?
  fi
  printf '%s\n\n%s\n' "$OUT" "$RECON_OUT"
  rc=$exec_rc
  [ "$reconcile_rc" -ne 0 ] && rc=$reconcile_rc
  echo "Exit code: $rc"

  if [ "$rc" -ne 0 ]; then
    notify "Veto" "Stock execution FAILED (exit $rc) — results/stock_execution.log"
  else
    heartbeat "$REPO_DIR/results/.last_success_stockexecution"
  fi
} >> "$LOG" 2>&1
exit "$rc"
