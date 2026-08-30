#!/bin/bash
# Install user systemd timers for the Veto paper loop (fake money).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNIT_DIR"

for src in "$REPO_DIR"/scripts/systemd/veto-*.service "$REPO_DIR"/scripts/systemd/veto-*.timer; do
  dest="$UNIT_DIR/$(basename "$src")"
  sed "s|__REPO__|$REPO_DIR|g" "$src" > "$dest"
done

systemctl --user daemon-reload
echo "Installed Veto paper timers from $REPO_DIR"
echo
echo "Enable (Alpaca PAPER account, fake money — PK keys in .env):"
echo "  systemctl --user enable --now veto-paperscan.timer veto-stockexecution.timer veto-stopmonitor.timer"
echo "  loginctl enable-linger \$USER   # optional: run while logged out"
echo
echo "Preview first (no ledger writes, no paper orders):"
echo "  DRY_RUN=1 bash $REPO_DIR/scripts/daily_paper_run.sh"
echo "  tail $REPO_DIR/results/paper_scan.log"
echo
echo "Disable:"
echo "  systemctl --user disable --now veto-paperscan.timer veto-stockexecution.timer veto-stopmonitor.timer"
