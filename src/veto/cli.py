"""Command-line entry for the fail-closed paper desk."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_run_config
from .desk import RunSafetyError, VetoDesk
from .ledger import RunLedger

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO / "config" / "veto.yaml"
DEFAULT_LEDGER = REPO / "results" / "veto" / "ledger.sqlite"


def _cfg(path: str | None):
    return load_run_config(path or DEFAULT_CONFIG)


def _ledger(path: str | None) -> RunLedger:
    return RunLedger(path or DEFAULT_LEDGER)


def cmd_fingerprint(args) -> int:
    cfg = _cfg(args.config)
    print(f"run_id={cfg.run_id}")
    print(f"fingerprint={cfg.fingerprint}")
    print("paper_only=true")
    return 0


def cmd_status(args) -> int:
    from .broker import PaperBroker

    broker = PaperBroker()
    acct = broker.account()
    positions = broker.positions()
    print("Alpaca paper account (fake money):")
    print(f"  status:        {acct['status']}")
    print(f"  equity:        ${acct['equity']:,.2f}")
    print(f"  cash:          ${acct['cash']:,.2f}")
    print(f"  buying_power:  ${acct['buying_power']:,.2f}")
    print(f"  options_level: {acct['options_approved_level']}")
    print(f"  positions:     {len(positions)}")
    if positions:
        for p in positions:
            print(f"    {p['symbol']} qty={p['qty']}")
    return 0


def cmd_init(args) -> int:
    cfg = _cfg(args.config)
    ledger = _ledger(args.ledger)
    try:
        if args.offline:
            ledger.initialize_run(cfg, broker_account_id="offline")
            print(f"Initialized {cfg.run_id} (offline)")
            print(f"  manifest: {cfg.fingerprint}")
            print(f"  ledger:   {ledger.path}")
            return 0
        from .broker import PaperBroker

        desk = VetoDesk(cfg, ledger, PaperBroker())
        account = desk.initialize()
        print(f"Initialized {cfg.run_id} against paper account")
        print(f"  equity:   ${account['equity']:,.2f}")
        print(f"  cash:     ${account['cash']:,.2f}")
        print(f"  options:  level {account['options_approved_level']}")
        print(f"  manifest: {cfg.fingerprint}")
        print(f"  ledger:   {ledger.path}")
        if account["options_approved_level"] < 2:
            print("  warning: options level < 2; the collar overlay may be rejected")
    except RunSafetyError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        ledger.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="veto", description="Fail-closed Alpaca paper agent")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = parser.add_subparsers(dest="cmd", required=True)

    fp = sub.add_parser("fingerprint", help="print the frozen manifest hash")
    fp.set_defaults(func=cmd_fingerprint)

    st = sub.add_parser("status", help="show paper equity, cash, positions (needs .env)")
    st.set_defaults(func=cmd_status)

    ini = sub.add_parser("init", help="initialize the frozen run ledger")
    ini.add_argument("--offline", action="store_true", help="ledger only; skip broker checks")
    ini.add_argument("--ledger", default=None)
    ini.set_defaults(func=cmd_init)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
