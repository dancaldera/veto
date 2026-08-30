#!/bin/bash
# Daily closed-bar scan + crypto execute + reconcile on the Alpaca PAPER account.
# Fake money only. Invoked at 00:05 UTC by veto-paperscan.timer.
#
# DRY_RUN=1 bash scripts/daily_paper_run.sh   # evaluate, do not write/submit
set -u

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR" || exit 1
# shellcheck source=scripts/_lib.sh
source "$REPO_DIR/scripts/_lib.sh"

LOG="$REPO_DIR/results/paper_scan.log"
rotate_log "$LOG"
VETO="$(veto_bin "$REPO_DIR")"
EXTRA=""
[ "${DRY_RUN:-0}" = "1" ] && EXTRA="--dry-run"

{
  echo "===================================================================="
  echo "Veto daily paper run: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "repo=$REPO_DIR  dry_run=${DRY_RUN:-0}  paper_only=true"

  SCAN_OUT="$("$VETO" scan $EXTRA 2>&1)"
  scan_rc=$?
  EXEC_OUT="$("$VETO" execute --asset crypto $EXTRA 2>&1)"
  exec_rc=$?
  if [ "${DRY_RUN:-0}" = "1" ]; then
    RECON_OUT="dry run — reconciliation skipped"
    reconcile_rc=0
  else
    RECON_OUT="$("$VETO" reconcile 2>&1)"
    reconcile_rc=$?
  fi
  printf '%s\n\n%s\n\n%s\n' "$SCAN_OUT" "$EXEC_OUT" "$RECON_OUT"
  rc=$scan_rc
  [ "$exec_rc" -ne 0 ] && rc=$exec_rc
  [ "$reconcile_rc" -ne 0 ] && rc=$reconcile_rc
  echo "Exit code: $rc"

  if [ "$rc" -ne 0 ]; then
    notify "Veto" "Daily paper-scan FAILED (exit $rc) — results/paper_scan.log"
  else
    heartbeat "$REPO_DIR/results/.last_success_paperscan"
  fi
} >> "$LOG" 2>&1
exit "$rc"
