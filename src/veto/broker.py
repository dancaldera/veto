"""Alpaca paper broker. paper=True is hardcoded; there is no live path."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]


class BrokerError(RuntimeError):
    """Missing paper credentials or a rejected paper-only operation."""


def load_paper_env() -> None:
    """Load repo `.env` if present. Never logs values."""
    path = REPO / ".env"
    if path.exists():
        load_dotenv(path, override=False)


def _require_paper_keys() -> tuple[str, str]:
    load_paper_env()
    key = os.getenv("ALPACA_API_KEY") or ""
    secret = os.getenv("ALPACA_SECRET_KEY") or ""
    if not key or not secret:
        raise BrokerError(
            "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env (paper keys only)."
        )
    if key.startswith("AK"):
        raise BrokerError(
            "ALPACA_API_KEY looks like a live key (AK…). Veto only accepts paper keys (PK…)."
        )
    return key, secret


class PaperBroker:
    def __init__(self, api_key: str | None = None, secret_key: str | None = None):
        if api_key is None or secret_key is None:
            api_key, secret_key = _require_paper_keys()
        try:
            from alpaca.trading.client import TradingClient
        except ImportError as exc:
            raise BrokerError("Install alpaca-py: pip install -e '.[broker]'") from exc
        # paper=True is not configurable. Live trading is off.
        self.client = TradingClient(api_key, secret_key, paper=True)

    def account(self) -> dict[str, Any]:
        a = self.client.get_account()
        return {
            "id": str(a.id),
            "status": str(getattr(a.status, "value", a.status)),
            "equity": float(a.equity),
            "cash": float(a.cash),
            "buying_power": float(a.buying_power),
            "options_approved_level": int(getattr(a, "options_approved_level", 0) or 0),
            "account_number": str(getattr(a, "account_number", "") or ""),
        }

    def positions(self) -> list[dict[str, Any]]:
        out = []
        for p in self.client.get_all_positions():
            out.append(
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "avg_entry": float(p.avg_entry_price),
                    "current_price": float(p.current_price) if p.current_price else None,
                }
            )
        return out

    def all_orders(self, after: datetime | None = None) -> list[dict[str, Any]]:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500, after=after)
        return [
            {
                "id": str(o.id),
                "symbol": str(o.symbol),
                "status": str(getattr(o.status, "value", o.status)),
                "side": str(getattr(o.side, "value", o.side)),
            }
            for o in self.client.get_orders(req)
        ]

    def clock(self) -> dict[str, Any]:
        value = self.client.get_clock()
        return {
            "is_open": bool(value.is_open),
            "timestamp": value.timestamp.isoformat(),
            "next_open": value.next_open.isoformat(),
            "next_close": value.next_close.isoformat(),
        }
