"""Offline scan: closed-bar signal, ranked by strength, gated by risk. No broker."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .config import RunConfig
from .ledger import RunLedger
from .risk import check_entry
from .signals import cross_strength, sma_cross_signal


def _bar_end(frame: pd.DataFrame) -> str:
    ts = pd.Timestamp(frame.index[-1])
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.isoformat()


def rank_buy_candidates(
    cfg: RunConfig,
    bars: Mapping[str, pd.DataFrame],
) -> list[tuple[str, str, float, float]]:
    """BUY candidates as (symbol, asset, strength, close), strongest first."""
    rows: list[tuple[str, str, float, float]] = []
    for symbol, asset in cfg.symbols:
        frame = bars.get(symbol)
        if frame is None or frame.empty:
            continue
        if sma_cross_signal(frame["Close"], cfg.strategy.fast_window, cfg.strategy.slow_window) != "BUY":
            continue
        strength = cross_strength(frame["Close"], cfg.strategy.fast_window, cfg.strategy.slow_window)
        price = float(frame["Close"].iloc[-1])
        rows.append((symbol, asset, strength, price))
    rows.sort(key=lambda item: (-(item[2] if item[2] == item[2] else float("-inf")), item[0]))
    return rows


class VetoDesk:
    def __init__(self, cfg: RunConfig, ledger: RunLedger):
        self.cfg = cfg
        self.ledger = ledger

    def scan(self, bars: Mapping[str, pd.DataFrame], record: bool = True) -> list[dict[str, Any]]:
        self.ledger.assert_manifest(self.cfg)
        results: list[dict[str, Any]] = []
        ranked = rank_buy_candidates(self.cfg, bars)
        buy_rank = {symbol: i for i, (symbol, *_rest) in enumerate(ranked)}

        # Walk every symbol so SELL/HOLD still get a row, but BUY intents
        # are attempted in strength order so the 8 slots are not alphabetical.
        scan_order: list[tuple[str, str]] = []
        seen: set[str] = set()
        for symbol, asset, _strength, _price in ranked:
            scan_order.append((symbol, asset))
            seen.add(symbol)
        for symbol, asset in self.cfg.symbols:
            if symbol not in seen:
                scan_order.append((symbol, asset))

        for portfolio in self.cfg.research.arms:
            for symbol, asset in scan_order:
                frame = bars.get(symbol)
                if frame is None or frame.empty:
                    results.append(
                        {
                            "symbol": symbol,
                            "portfolio": portfolio,
                            "action": "none",
                            "reason": "missing_bars",
                        }
                    )
                    continue
                signal = sma_cross_signal(
                    frame["Close"], self.cfg.strategy.fast_window, self.cfg.strategy.slow_window
                )
                strength = cross_strength(
                    frame["Close"], self.cfg.strategy.fast_window, self.cfg.strategy.slow_window
                )
                price = float(frame["Close"].iloc[-1])
                holding = symbol in {
                    s: p
                    for s, p in self.ledger.positions(self.cfg.run_id, portfolio).items()
                    if p.asset != "option"
                }
                action, reason, status = "none", "no_fresh_cross", "recorded"
                if signal == "BUY" and not holding:
                    risk = check_entry(self.cfg, self.ledger, portfolio, symbol, asset, bars)
                    if risk.allowed:
                        action, reason, status = "buy_intent", "allowed", "pending"
                    else:
                        reason = risk.reason
                elif signal == "SELL" and holding:
                    action, reason, status = "sell_intent", "reverse_cross", "pending"
                elif holding:
                    reason = "holding"

                row = {
                    "run_id": self.cfg.run_id,
                    "portfolio": portfolio,
                    "symbol": symbol,
                    "asset": asset,
                    "strategy": self.cfg.strategy.name,
                    "bar_end": _bar_end(frame),
                    "signal": signal,
                    "signal_price": str(price),
                    "notional": str(self.cfg.portfolio.position_notional),
                    "strength": None if strength != strength else float(strength),
                    "rank": buy_rank.get(symbol),
                    "action": action,
                    "reason": reason,
                    "status": status,
                    "config_hash": self.cfg.fingerprint,
                }
                decision_id = self.ledger.record_decision(row) if record else "dry-run"
                results.append({**row, "decision_id": decision_id})
        return results
