"""Defined-risk 1-lot collar overlay: long ~8% OTM put, short ~8% OTM call."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable


MULTIPLIER = 100


@dataclass(frozen=True)
class OptionQuote:
    symbol: str
    option_type: str  # "put" | "call"
    strike: float
    expiration: date
    bid: float | None = None
    ask: float | None = None
    close: float | None = None

    @property
    def mid(self) -> float | None:
        if self.bid is not None and self.ask is not None and self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        if self.ask is not None and self.ask > 0:
            return self.ask
        if self.close is not None and self.close > 0:
            return self.close
        return None


@dataclass(frozen=True)
class CollarPlan:
    put: OptionQuote
    call: OptionQuote
    dte: int
    estimated_debit: float
    limit_price: float

    def as_dict(self) -> dict:
        return {
            "put": self.put.symbol,
            "call": self.call.symbol,
            "put_strike": self.put.strike,
            "call_strike": self.call.strike,
            "expiration": self.put.expiration.isoformat(),
            "dte": self.dte,
            "estimated_debit": round(self.estimated_debit, 2),
            "limit_price": self.limit_price,
        }


def _nearest_expiration(exps: Iterable[date], target: date) -> date | None:
    unique = sorted(set(exps))
    if not unique:
        return None
    return min(unique, key=lambda exp: abs((exp - target).days))


def pick_collar(
    contracts: list[OptionQuote],
    spot: float,
    *,
    put_otm_pct: float = 8,
    call_otm_pct: float = 8,
    target_dte: int = 35,
    today: date | None = None,
) -> CollarPlan | None:
    """Pick 1 put + 1 call on the expiry closest to target DTE."""
    if spot <= 0 or not contracts:
        return None
    today = today or date.today()
    target_exp = today + timedelta(days=target_dte)
    expiry = _nearest_expiration((c.expiration for c in contracts if c.expiration >= today), target_exp)
    if expiry is None:
        return None
    put_strike = spot * (1 - put_otm_pct / 100)
    call_strike = spot * (1 + call_otm_pct / 100)
    puts = [c for c in contracts if c.option_type == "put" and c.expiration == expiry and c.strike <= put_strike]
    calls = [c for c in contracts if c.option_type == "call" and c.expiration == expiry and c.strike >= call_strike]
    if not puts or not calls:
        return None
    put = max(puts, key=lambda c: c.strike)
    call = min(calls, key=lambda c: c.strike)
    put_px = put.ask if put.ask and put.ask > 0 else put.mid
    call_px = call.bid if call.bid and call.bid > 0 else call.mid
    if put_px is None:
        return None
    call_credit = call_px or 0.0
    debit_per_share = put_px - call_credit
    estimated = max(0.0, debit_per_share) * MULTIPLIER
    # Limit is net debit per share (Alpaca mleg convention). Floor at $0.01.
    limit = max(0.01, round(debit_per_share, 2)) if debit_per_share > 0 else 0.01
    return CollarPlan(
        put=put,
        call=call,
        dte=(expiry - today).days,
        estimated_debit=estimated,
        limit_price=limit,
    )
