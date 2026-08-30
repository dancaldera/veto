"""MCP surface: inspect, explain, preview. Default dry-run. No unconstrained buy."""

from __future__ import annotations

from .broker import PaperBroker, _require_paper_keys
from .bars import fetch_watchlist
from .cli import DEFAULT_CONFIG, DEFAULT_LEDGER
from .config import load_run_config
from .desk import VetoDesk
from .ledger import RunLedger


def _desk() -> VetoDesk:
    _require_paper_keys()
    cfg = load_run_config(DEFAULT_CONFIG)
    ledger = RunLedger(DEFAULT_LEDGER)
    ledger.assert_manifest(cfg)
    return VetoDesk(cfg, ledger, PaperBroker())


def build_server():
    try:
        from fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("Install FastMCP: pip install -e '.[mcp]'") from exc

    mcp = FastMCP(
        "veto",
        instructions=(
            "Veto is a fail-closed Alpaca paper desk. You may inspect account, "
            "decisions, halt status, and collar previews. scan_now and "
            "execute_pending default to dry_run=true. There is no buy(symbol, qty) tool."
        ),
    )

    @mcp.tool
    def get_account() -> dict:
        """Paper account equity, cash, and options approval level."""
        return _desk().broker.account()

    @mcp.tool
    def get_positions() -> list:
        """Open paper positions."""
        return _desk().broker.positions()

    @mcp.tool
    def get_halt_status() -> dict:
        """Whether new buys are halted, and why (unknown fill, qty mismatch, or drawdown)."""
        return _desk().halt_status()

    @mcp.tool
    def latest_decisions(limit: int = 20) -> list:
        """Recent baseline decisions from the ledger."""
        desk = _desk()
        rows = desk.ledger.decisions(desk.cfg.run_id, "baseline")[-limit:]
        return [
            {
                "symbol": r["symbol"],
                "signal": r["signal"],
                "action": r["action"],
                "reason": r["reason"],
                "status": r["status"],
                "bar_end": r["bar_end"],
            }
            for r in rows
        ]

    @mcp.tool
    def explain_decision(symbol: str) -> dict:
        """Explain the latest baseline decision for a symbol (the veto reason)."""
        symbol = symbol if "/" in symbol else symbol.upper()
        return _desk().explain_decision(symbol)

    @mcp.tool
    def preview_collar(symbol: str) -> dict:
        """Preview the 1-lot put/call overlay. Does not place an order."""
        return _desk().preview_collar(symbol.upper())

    @mcp.tool
    def scan_now(dry_run: bool = True) -> dict:
        """Scan closed daily bars. Defaults to dry_run so the ledger is unchanged."""
        desk = _desk()
        bars = fetch_watchlist(desk.cfg)
        rows = desk.scan(bars, record=not dry_run)
        baseline = [r for r in rows if r.get("portfolio") == "baseline"]
        return {
            "dry_run": dry_run,
            "rows": [
                {
                    "symbol": r.get("symbol"),
                    "signal": r.get("signal"),
                    "action": r.get("action"),
                    "reason": r.get("reason"),
                }
                for r in baseline
            ],
        }

    @mcp.tool
    def execute_pending(asset: str, dry_run: bool = True) -> list:
        """Execute pending stock or crypto intents. Defaults to dry_run."""
        if asset not in {"stock", "crypto"}:
            return [{"error": "asset must be stock or crypto"}]
        return _desk().execute_pending(asset, dry_run=dry_run)

    return mcp


def main() -> None:
    _require_paper_keys()
    build_server().run()


if __name__ == "__main__":
    main()
