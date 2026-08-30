"""Alpaca paper broker. paper=True is hardcoded; there is no live path."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .options import CollarPlan, OptionQuote

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
        self._api_key = api_key
        self._secret_key = secret_key
        self._stock_data = None
        self._crypto_data = None
        self._option_data = None

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

    def latest_price(self, symbol: str, asset: str) -> float:
        if asset == "crypto":
            from alpaca.data.historical import CryptoHistoricalDataClient
            from alpaca.data.requests import CryptoLatestTradeRequest

            if self._crypto_data is None:
                self._crypto_data = CryptoHistoricalDataClient(self._api_key, self._secret_key)
            trades = self._crypto_data.get_crypto_latest_trade(
                CryptoLatestTradeRequest(symbol_or_symbols=symbol)
            )
            return float(trades[symbol].price)
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest

        if self._stock_data is None:
            self._stock_data = StockHistoricalDataClient(self._api_key, self._secret_key)
        trades = self._stock_data.get_stock_latest_trade(
            StockLatestTradeRequest(symbol_or_symbols=symbol)
        )
        return float(trades[symbol].price)

    def buy_limit(
        self,
        symbol: str,
        notional: float,
        asset: str,
        limit_price: float,
        client_order_id: str,
    ) -> dict[str, Any]:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest

        tif = TimeInForce.IOC if asset == "crypto" else TimeInForce.DAY
        req = LimitOrderRequest(
            symbol=symbol,
            notional=round(float(notional), 2),
            limit_price=quantize_limit_price(limit_price, asset),
            side=OrderSide.BUY,
            time_in_force=tif,
            client_order_id=client_order_id,
        )
        return self._order_dict(self.client.submit_order(req))

    def close(self, symbol: str) -> str:
        order = self.client.close_position(symbol.replace("/", ""))
        return str(order.id)

    def option_quotes(
        self, symbol: str, *, put_otm_pct: float, call_otm_pct: float, target_dte: int, spot: float
    ) -> list[OptionQuote]:
        from alpaca.trading.enums import AssetStatus, ContractType
        from alpaca.trading.requests import GetOptionContractsRequest

        today = date.today()
        lo = today + timedelta(days=max(7, target_dte - 15))
        hi = today + timedelta(days=target_dte + 15)
        out: list[OptionQuote] = []
        for kind, strike_filter in (
            (ContractType.PUT, {"strike_price_lte": f"{spot * (1 - put_otm_pct / 100):.2f}"}),
            (ContractType.CALL, {"strike_price_gte": f"{spot * (1 + call_otm_pct / 100):.2f}"}),
        ):
            req = GetOptionContractsRequest(
                underlying_symbols=[symbol],
                status=AssetStatus.ACTIVE,
                type=kind,
                expiration_date_gte=lo.isoformat(),
                expiration_date_lte=hi.isoformat(),
                limit=200,
                **strike_filter,
            )
            payload = self.client.get_option_contracts(req)
            contracts = getattr(payload, "option_contracts", None) or []
            for c in contracts:
                out.append(
                    OptionQuote(
                        symbol=str(c.symbol),
                        option_type=str(getattr(c.type, "value", c.type)).lower(),
                        strike=float(c.strike_price),
                        expiration=c.expiration_date
                        if isinstance(c.expiration_date, date)
                        else date.fromisoformat(str(c.expiration_date)),
                        close=float(c.close_price) if c.close_price else None,
                    )
                )
        return self._fill_option_quotes(out)

    def _fill_option_quotes(self, contracts: list[OptionQuote]) -> list[OptionQuote]:
        if not contracts:
            return contracts
        try:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.requests import OptionLatestQuoteRequest
        except ImportError:
            return contracts
        if self._option_data is None:
            self._option_data = OptionHistoricalDataClient(self._api_key, self._secret_key)
        symbols = [c.symbol for c in contracts]
        try:
            quotes = self._option_data.get_option_latest_quote(
                OptionLatestQuoteRequest(symbol_or_symbols=symbols)
            )
        except Exception:
            return contracts
        filled = []
        for c in contracts:
            q = quotes.get(c.symbol) if isinstance(quotes, dict) else None
            bid = float(q.bid_price) if q and getattr(q, "bid_price", None) else c.bid
            ask = float(q.ask_price) if q and getattr(q, "ask_price", None) else c.ask
            filled.append(
                OptionQuote(
                    symbol=c.symbol,
                    option_type=c.option_type,
                    strike=c.strike,
                    expiration=c.expiration,
                    bid=bid,
                    ask=ask,
                    close=c.close,
                )
            )
        return filled

    def submit_collar(self, plan: CollarPlan, client_order_id: str) -> dict[str, Any]:
        from alpaca.trading.enums import OrderClass, OrderSide, PositionIntent, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

        req = LimitOrderRequest(
            qty=1,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.MLEG,
            limit_price=plan.limit_price,
            client_order_id=client_order_id,
            legs=[
                OptionLegRequest(
                    symbol=plan.put.symbol,
                    ratio_qty=1,
                    side=OrderSide.BUY,
                    position_intent=PositionIntent.BUY_TO_OPEN,
                ),
                OptionLegRequest(
                    symbol=plan.call.symbol,
                    ratio_qty=1,
                    side=OrderSide.SELL,
                    position_intent=PositionIntent.SELL_TO_OPEN,
                ),
            ],
        )
        return self._order_dict(self.client.submit_order(req))

    @staticmethod
    def _order_dict(order: Any) -> dict[str, Any]:
        return {
            "id": str(order.id),
            "client_order_id": str(getattr(order, "client_order_id", "") or ""),
            "symbol": str(getattr(order, "symbol", "") or ""),
            "status": str(getattr(getattr(order, "status", ""), "value", getattr(order, "status", ""))),
            "side": str(getattr(getattr(order, "side", ""), "value", getattr(order, "side", ""))),
            "submitted_at": order.submitted_at.isoformat() if getattr(order, "submitted_at", None) else None,
            "filled_qty": float(getattr(order, "filled_qty", 0) or 0),
        }


def quantize_limit_price(price: float, asset: str) -> float:
    value = Decimal(str(price))
    if asset == "crypto":
        quantum = Decimal("0.00000001")
    elif abs(value) < Decimal("1"):
        quantum = Decimal("0.0001")
    else:
        quantum = Decimal("0.01")
    return float(value.quantize(quantum, rounding=ROUND_HALF_UP))
