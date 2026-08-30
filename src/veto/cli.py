"""Command-line entry: `veto fingerprint` and offline `veto init`."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_run_config
from .ledger import RunLedger

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO / "config" / "veto.yaml"
DEFAULT_LEDGER = REPO / "results" / "veto" / "ledger.sqlite"


def _cfg(path: str | None):
    return load_run_config(path or DEFAULT_CONFIG)


def cmd_fingerprint(args) -> int:
    cfg = _cfg(args.config)
    print(f"run_id={cfg.run_id}")
    print(f"fingerprint={cfg.fingerprint}")
    print("paper_only=true")
    return 0


def cmd_init(args) -> int:
    cfg = _cfg(args.config)
    if not args.offline:
        raise SystemExit(
            "Live init needs the $100k paper account (Step 1). "
            "Reset Alpaca paper to $100,000 with no positions or orders, "
            "then re-run. For a local ledger only: veto init --offline"
        )
    ledger = RunLedger(args.ledger or DEFAULT_LEDGER)
    try:
        ledger.initialize_run(cfg, broker_account_id="offline")
        print(f"Initialized {cfg.run_id} (offline)")
        print(f"  manifest: {cfg.fingerprint}")
        print(f"  ledger:   {ledger.path}")
    finally:
        ledger.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="veto", description="Fail-closed Alpaca paper agent")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = parser.add_subparsers(dest="cmd", required=True)

    fp = sub.add_parser("fingerprint", help="print the frozen manifest hash")
    fp.set_defaults(func=cmd_fingerprint)

    ini = sub.add_parser("init", help="initialize the frozen run ledger")
    ini.add_argument("--offline", action="store_true", help="ledger only; skip broker checks")
    ini.add_argument("--ledger", default=None)
    ini.set_defaults(func=cmd_init)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
