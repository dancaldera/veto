# Paper schedule (Linux)

Veto talks only to Alpaca **paper** (`paper=True` hardcoded; `PK…` keys; no live path). A HOLD tape is a valid evaluation. Do not invent an SMA cross.

## How to show it works (for the video)

1. Public demo: [https://bszv8nabdvvipmbetdvtgv.streamlit.app/](https://bszv8nabdvvipmbetdvtgv.streamlit.app/) — $100k equity, dry scan, collar preview, **no buy button**.
2. CLI: `veto scan --dry-run` (17× HOLD today is allowed) → `veto preview-collar AAPL` → `veto reconcile`.
3. Tests: `pytest -q`.
4. Prior research: [docs/prior-research.md](prior-research.md) (+5.4% vs +59%, not this week’s P&L).

If a **fresh** SMA cross appears later this week, the schedule below may submit a **paper** order (fake money). Never force one.

## Wrappers

| When | Script | What |
|---|---|---|
| 00:05 UTC daily | `scripts/daily_paper_run.sh` | closed-bar scan, crypto execute, reconcile |
| 09:31 America/New_York weekdays | `scripts/execute_stock_intents.sh` | stock execute (defers if the cash session is closed), reconcile |
| every 30 minutes | `scripts/intraday_stop_run.sh` | 8% poll stop (skip if a collar is live), reconcile |

Logs: `results/paper_scan.log`, `results/stock_execution.log`, `results/stop_monitor.log` (gitignored).

```bash
# Preview — no ledger writes, no paper orders
DRY_RUN=1 bash scripts/daily_paper_run.sh
tail results/paper_scan.log

# Real paper loop (still fake money)
bash scripts/install-timers.sh
systemctl --user enable --now veto-paperscan.timer veto-stockexecution.timer veto-stopmonitor.timer
loginctl enable-linger $USER   # optional: keep timers after logout
systemctl --user list-timers 'veto-*'
```
