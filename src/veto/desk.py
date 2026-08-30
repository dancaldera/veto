"""Scan, ranked by strength, then gap-capped paper execution."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
from typing import Any, Mapping

import pandas as pd

from .alpaca_cli import format_collar_command
from .broker import PaperBroker
from .config import RunConfig
from .ledger import RunLedger, utc_now
from .options import pick_collar
from .risk import check_entry, check_overlay, drawdown_pct
from .signals import cross_strength, sma_cross_signal


class RunSafetyError(RuntimeError):
    """Raised when an operation would violate the paper-run contract."""


def _asset_from_broker_symbol(cfg: RunConfig, symbol: str) -> tuple[str, str]:
    target = symbol.replace("/", "")
    for configured, asset in cfg.symbols:
        if configured.replace("/", "") == target:
            return configured, asset
    return symbol, ""


def _is_option_broker_position(position: Mapping[str, Any]) -> bool:
    asset_class = str(position.get("asset_class") or "").lower()
    return asset_class in {"option", "us_option"}


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
    def __init__(self, cfg: RunConfig, ledger: RunLedger, broker: PaperBroker | None = None):
        self.cfg = cfg
        self.ledger = ledger
        self.broker = broker

    def initialize(self) -> dict[str, Any]:
        if self.broker is None:
            raise RunSafetyError("A paper broker is required to initialize a run")
        account = self.broker.account()
        positions = self.broker.positions()
        orders = self.broker.all_orders()
        if abs(account["equity"] - self.cfg.starting_equity) > 1:
            raise RunSafetyError(
                f"Paper equity must be ${self.cfg.starting_equity:,.2f}; got ${account['equity']:,.2f}"
            )
        if abs(account["cash"] - self.cfg.starting_equity) > 1:
            raise RunSafetyError(
                f"Paper cash must be ${self.cfg.starting_equity:,.2f}; got ${account['cash']:,.2f}"
            )
        if positions or orders:
            raise RunSafetyError("Paper account must be clean: no positions and no order history")
        self.ledger.initialize_run(self.cfg, account["id"])
        self.record_account_snapshot(account)
        return account

    def scan(self, bars: Mapping[str, pd.DataFrame], record: bool = True) -> list[dict[str, Any]]:
        if record:
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

    def explain_decision(self, symbol: str) -> dict[str, Any]:
        self.ledger.assert_manifest(self.cfg)
        rows = [
            d
            for d in self.ledger.decisions(self.cfg.run_id, "baseline")
            if d["symbol"] == symbol
        ]
        run = self.ledger.run(self.cfg.run_id)
        halted = self.ledger.is_halted(self.cfg.run_id)
        if not rows:
            return {
                "symbol": symbol,
                "reason": "no_decision",
                "halted": halted,
                "halt_reason": run["halt_reason"] if run else None,
            }
        d = rows[-1]
        return {
            "symbol": d["symbol"],
            "asset": d["asset"],
            "signal": d["signal"],
            "action": d["action"],
            "reason": d["reason"],
            "status": d["status"],
            "bar_end": d["bar_end"],
            "signal_price": d["signal_price"],
            "halted": halted,
            "halt_reason": run["halt_reason"] if run else None,
        }

    def halt_status(self) -> dict[str, Any]:
        run = self.ledger.assert_manifest(self.cfg)
        snap = self.ledger.latest_equity(self.cfg.run_id)
        return {
            "run_id": self.cfg.run_id,
            "halted": self.ledger.is_halted(self.cfg.run_id),
            "status": run["status"],
            "halt_reason": run["halt_reason"],
            "equity": float(snap["equity"]) if snap else None,
            "drawdown_pct": float(snap["drawdown_pct"]) if snap else None,
            "captured_at": snap["captured_at"] if snap else None,
        }

    def preview_collar(self, symbol: str, spot: float | None = None) -> dict[str, Any]:
        if self.broker is None:
            raise RunSafetyError("A paper broker is required to preview a collar")
        price = spot if spot is not None else self.broker.latest_price(symbol, "stock")
        quotes = self.broker.option_quotes(
            symbol,
            put_otm_pct=self.cfg.options.put_otm_pct,
            call_otm_pct=self.cfg.options.call_otm_pct,
            target_dte=self.cfg.options.target_dte,
            spot=price,
        )
        plan = pick_collar(
            quotes,
            price,
            put_otm_pct=self.cfg.options.put_otm_pct,
            call_otm_pct=self.cfg.options.call_otm_pct,
            target_dte=self.cfg.options.target_dte,
        )
        if plan is None:
            return {"symbol": symbol, "spot": price, "ok": False, "reason": "no_collar_contracts"}
        overlay = check_overlay(
            self.cfg, self.ledger, "baseline", symbol, estimated_debit=plan.estimated_debit
        )
        return {
            "symbol": symbol,
            "spot": price,
            "ok": overlay.allowed,
            "reason": overlay.reason,
            "cli": format_collar_command(plan),
            **plan.as_dict(),
        }

    def execute_pending(self, asset: str, dry_run: bool = False) -> list[dict[str, Any]]:
        self.ledger.assert_manifest(self.cfg)
        if self.broker is None and not dry_run:
            raise RunSafetyError("A paper broker is required to execute intents")
        if asset == "stock" and self.broker is not None and not self.broker.clock()["is_open"]:
            return [{"action": "deferred_market_closed"}]
        out: list[dict[str, Any]] = []
        pending = [
            d
            for d in self.ledger.decisions(self.cfg.run_id, "baseline", "pending")
            if d["asset"] == asset
        ]
        for d in pending:
            if d["action"] == "buy_intent":
                out.append(self._execute_buy(d, dry_run=dry_run))
            elif d["action"] == "sell_intent":
                out.append(self._execute_sell(d, dry_run=dry_run))
        return out

    def _execute_buy(self, d, *, dry_run: bool) -> dict[str, Any]:
        if self.ledger.is_halted(self.cfg.run_id):
            self.ledger.set_decision_status(d["decision_id"], "expired", "run_halted")
            return {"decision_id": d["decision_id"], "action": "expired_halt"}
        asset = d["asset"]
        gap = self.cfg.gap_limit_pct(asset) / 100
        raw_limit = float(d["signal_price"]) * (1 + gap)
        current = (
            self.broker.latest_price(d["symbol"], asset)
            if self.broker
            else float(d["signal_price"])
        )
        if current > raw_limit:
            self.ledger.set_decision_status(
                d["decision_id"], "expired", f"adverse_gap:{current:.8f}"
            )
            return {"decision_id": d["decision_id"], "action": "expired_gap", "price": current}
        from .broker import quantize_limit_price

        limit_price = quantize_limit_price(raw_limit, asset)
        if dry_run:
            overlay = None
            if asset == "stock" and self.broker is not None:
                overlay = self.preview_collar(d["symbol"], spot=current)
            return {
                "decision_id": d["decision_id"],
                "action": "would_buy",
                "limit_price": limit_price,
                "overlay": overlay,
            }
        client_id = f"veto-{d['decision_id'][:12]}-buy"
        order = self.broker.buy_limit(
            d["symbol"], float(d["notional"]), asset, limit_price, client_id
        )
        self.ledger.record_order(
            {
                "run_id": self.cfg.run_id,
                "decision_id": d["decision_id"],
                "portfolio": "baseline",
                "client_order_id": client_id,
                "broker_order_id": order["id"],
                "symbol": d["symbol"],
                "asset": asset,
                "side": "buy",
                "requested_notional": d["notional"],
                "limit_price": str(limit_price),
                "status": order["status"],
                "submitted_at": order["submitted_at"],
            }
        )
        self.ledger.set_decision_status(d["decision_id"], "submitted")
        overlay_result = None
        if asset == "stock":
            overlay_result = self._submit_overlay(d, current)
        return {
            "decision_id": d["decision_id"],
            "action": "submitted",
            "order_id": order["id"],
            "overlay": overlay_result,
        }

    def _submit_overlay(self, d, spot: float) -> dict[str, Any]:
        preview = self.preview_collar(d["symbol"], spot=spot)
        if not preview.get("ok"):
            return {"action": "options_skipped", "reason": preview.get("reason", "not_allowed")}
        plan = pick_collar(
            self.broker.option_quotes(
                d["symbol"],
                put_otm_pct=self.cfg.options.put_otm_pct,
                call_otm_pct=self.cfg.options.call_otm_pct,
                target_dte=self.cfg.options.target_dte,
                spot=spot,
            ),
            spot,
            put_otm_pct=self.cfg.options.put_otm_pct,
            call_otm_pct=self.cfg.options.call_otm_pct,
            target_dte=self.cfg.options.target_dte,
        )
        if plan is None:
            return {"action": "options_skipped", "reason": "no_collar_contracts"}
        client_id = f"veto-{d['decision_id'][:12]}-collar"
        try:
            order = self.broker.submit_collar(plan, client_id)
        except Exception as exc:  # noqa: BLE001 — overlay must never fail the share buy
            return {"action": "options_skipped", "reason": f"submit_failed:{exc}"}
        overlay_id = self.ledger.record_decision(
            {
                "run_id": self.cfg.run_id,
                "portfolio": "baseline",
                "symbol": d["symbol"],
                "asset": "option",
                "strategy": "collar",
                "bar_end": d["bar_end"],
                "signal": "COLLAR",
                "signal_price": str(spot),
                "notional": str(plan.estimated_debit),
                "action": "collar_open",
                "reason": "allowed",
                "status": "submitted",
                "config_hash": self.cfg.fingerprint,
            }
        )
        self.ledger.record_order(
            {
                "run_id": self.cfg.run_id,
                "decision_id": overlay_id,
                "portfolio": "baseline",
                "client_order_id": client_id,
                "broker_order_id": order["id"],
                "symbol": d["symbol"],
                "asset": "option",
                "side": "buy",
                "requested_notional": str(plan.estimated_debit),
                "limit_price": str(plan.limit_price),
                "status": order["status"],
                "submitted_at": order["submitted_at"] or utc_now(),
            }
        )
        return {"action": "collar_submitted", "order_id": order["id"], **plan.as_dict()}

    def _execute_sell(self, d, *, dry_run: bool) -> dict[str, Any]:
        if dry_run:
            return {"decision_id": d["decision_id"], "action": "would_close"}
        order_id = self.broker.close(d["symbol"])
        client_id = f"veto-{d['decision_id'][:12]}-sell"
        self.ledger.record_order(
            {
                "run_id": self.cfg.run_id,
                "decision_id": d["decision_id"],
                "portfolio": "baseline",
                "client_order_id": client_id,
                "broker_order_id": order_id,
                "symbol": d["symbol"],
                "asset": d["asset"],
                "side": "sell",
                "status": "submitted",
                "submitted_at": utc_now(),
            }
        )
        self.ledger.set_decision_status(d["decision_id"], "submitted")
        return {"decision_id": d["decision_id"], "action": "submitted", "order_id": order_id}

    def check_stops(self, dry_run: bool = False) -> list[dict[str, Any]]:
        """8% fill-derived poll stop. Skip flatten when a collar put is live."""
        self.ledger.assert_manifest(self.cfg)
        if self.broker is None:
            raise RunSafetyError("A paper broker is required to check stops")
        collared = self.ledger.option_overlay_names(self.cfg.run_id, "baseline")
        broker_positions = {p["symbol"].replace("/", ""): p for p in self.broker.positions()}
        out: list[dict[str, Any]] = []
        for symbol, pos in self.ledger.positions(self.cfg.run_id, "baseline").items():
            if pos.asset == "option":
                continue
            if symbol in collared:
                out.append({"symbol": symbol, "action": "none", "reason": "collar_live"})
                continue
            broker_pos = broker_positions.get(symbol.replace("/", ""))
            if not broker_pos or broker_pos.get("current_price") is None:
                out.append({"symbol": symbol, "action": "none", "reason": "missing_broker_position"})
                continue
            price = Decimal(str(broker_pos["current_price"]))
            plpc = (price / pos.avg_entry - 1) * 100 if pos.avg_entry else Decimal(0)
            if plpc > -Decimal(str(self.cfg.strategy.stop_loss_pct)):
                out.append({"symbol": symbol, "action": "none", "plpc": float(plpc)})
                continue
            now = utc_now()
            decision_id = self.ledger.record_decision(
                {
                    "run_id": self.cfg.run_id,
                    "portfolio": "baseline",
                    "symbol": symbol,
                    "asset": pos.asset,
                    "strategy": "stop-monitor",
                    "bar_end": now,
                    "signal": "STOP",
                    "signal_price": str(price),
                    "notional": "0",
                    "action": "sell_intent",
                    "reason": f"stop:{float(plpc):.4f}%",
                    "status": "pending" if dry_run else "submitted",
                    "config_hash": self.cfg.fingerprint,
                }
            )
            if dry_run:
                out.append(
                    {
                        "symbol": symbol,
                        "action": "would_stop",
                        "plpc": float(plpc),
                        "decision_id": decision_id,
                    }
                )
                continue
            order_id = self.broker.close(symbol)
            client_id = f"veto-{decision_id[:12]}-stop"
            self.ledger.record_order(
                {
                    "run_id": self.cfg.run_id,
                    "decision_id": decision_id,
                    "portfolio": "baseline",
                    "client_order_id": client_id,
                    "broker_order_id": order_id,
                    "symbol": symbol,
                    "asset": pos.asset,
                    "side": "sell",
                    "status": "submitted",
                    "submitted_at": now,
                }
            )
            out.append(
                {
                    "symbol": symbol,
                    "action": "stopped",
                    "plpc": float(plpc),
                    "order_id": order_id,
                    "decision_id": decision_id,
                }
            )
        return out

    def reconcile(self) -> dict[str, Any]:
        """Import paper fills/fees. Halt new buys on unknown orders or qty mismatch."""
        self.ledger.assert_manifest(self.cfg)
        if self.broker is None:
            raise RunSafetyError("A paper broker is required to reconcile")
        run = self.ledger.run(self.cfg.run_id)
        after = run["started_at"] if run else None
        unknown_orders: list[str] = []
        new_fills = 0
        for activity in self.broker.activities("FILL", after):
            broker_order_id = str(activity.get("order_id", "") or "")
            order = (
                self.ledger.order_by_broker_id(self.cfg.run_id, broker_order_id)
                if broker_order_id
                else None
            )
            if order:
                symbol, asset = order["symbol"], order["asset"]
            else:
                symbol, asset = _asset_from_broker_symbol(
                    self.cfg, str(activity.get("symbol", ""))
                )
                unknown_orders.append(broker_order_id or str(activity.get("id", "")))
            new_fills += int(
                self.ledger.record_fill(
                    {
                        "fill_id": str(activity.get("id")),
                        "run_id": self.cfg.run_id,
                        "order_pk": order["order_pk"] if order else None,
                        "decision_id": order["decision_id"] if order else None,
                        "portfolio": "baseline",
                        "broker_order_id": broker_order_id or None,
                        "symbol": symbol,
                        "asset": asset or "stock",
                        "side": str(activity.get("side", "")),
                        "qty": str(activity.get("qty", 0)),
                        "price": str(activity.get("price", 0)),
                        "transaction_time": str(activity.get("transaction_time") or utc_now()),
                    }
                )
            )

        started = datetime.fromisoformat(run["started_at"]) if run else None
        for broker_order in self.broker.all_orders(after=started):
            order = self.ledger.order_by_broker_id(self.cfg.run_id, broker_order["id"])
            if not order:
                unknown_orders.append(broker_order["id"])
                continue
            status = str(broker_order["status"]).lower()
            self.ledger.update_order_status(order["order_pk"], status)
            decision_id = order["decision_id"]
            if not decision_id:
                continue
            if float(broker_order.get("filled_qty") or 0) > 0 or status == "filled":
                self.ledger.set_decision_status(decision_id, "filled")
            elif status in {"canceled", "expired", "rejected", "done_for_day"}:
                decision_status = "rejected" if status == "rejected" else "expired"
                self.ledger.set_decision_status(decision_id, decision_status, f"broker:{status}")

        new_fees = 0
        for activity_type in ("CFEE", "FEE"):
            for activity in self.broker.activities(activity_type, after):
                amount = abs(Decimal(str(activity.get("net_amount") or 0)))
                if amount == 0 and activity.get("qty") and activity.get("price"):
                    amount = abs(Decimal(str(activity["qty"])) * Decimal(str(activity["price"])))
                new_fees += int(
                    self.ledger.record_fee(
                        {
                            "fee_id": str(activity.get("id")),
                            "run_id": self.cfg.run_id,
                            "broker_order_id": activity.get("order_id"),
                            "symbol": activity.get("symbol"),
                            "activity_type": activity_type,
                            "amount": str(amount),
                            "occurred_at": str(
                                activity.get("date") or activity.get("transaction_time") or utc_now()
                            ),
                            "raw_json": json.dumps(activity, default=str, sort_keys=True),
                        }
                    )
                )

        account = self.broker.account()
        broker_positions = {
            p["symbol"].replace("/", ""): Decimal(str(p["qty"]))
            for p in self.broker.positions()
            if not _is_option_broker_position(p)
        }
        ledger_positions = {
            s.replace("/", ""): p.qty for s, p in self.ledger.positions(self.cfg.run_id).items()
        }
        mismatches = []
        for symbol in sorted(set(broker_positions) | set(ledger_positions)):
            broker_qty = broker_positions.get(symbol, Decimal(0))
            ledger_qty = ledger_positions.get(symbol, Decimal(0))
            if abs(broker_qty - ledger_qty) > Decimal("0.00000001"):
                mismatches.append(symbol)

        unique_unknown = list(dict.fromkeys(unknown_orders))
        snap = self.record_account_snapshot(account)
        already_halted = self.ledger.is_halted(self.cfg.run_id)
        if unique_unknown or mismatches:
            self.ledger.halt(
                self.cfg.run_id,
                f"reconciliation_failed:unknown_orders={unique_unknown},qty={mismatches}",
            )
        elif not already_halted and snap["drawdown_pct"] >= self.cfg.portfolio.drawdown_halt_pct:
            self.ledger.halt(self.cfg.run_id, f"drawdown_halt:{snap['drawdown_pct']:.4f}%")

        run_after = self.ledger.run(self.cfg.run_id)
        return {
            "new_fills": new_fills,
            "new_fees": new_fees,
            "unknown_orders": unique_unknown,
            "quantity_mismatches": mismatches,
            "equity": account["equity"],
            "drawdown_pct": float(snap["drawdown_pct"]),
            "halted": self.ledger.is_halted(self.cfg.run_id),
            "halt_reason": run_after["halt_reason"] if run_after else None,
        }

    def record_account_snapshot(self, account: Mapping[str, Any]) -> dict[str, Any]:
        hwm = self.ledger.high_water(self.cfg.run_id) or Decimal(str(self.cfg.starting_equity))
        equity = float(account["equity"])
        hwm_float = max(float(hwm), equity)
        dd = drawdown_pct(equity, hwm_float)
        gross = sum(
            (p.cost_basis for p in self.ledger.positions(self.cfg.run_id).values()),
            Decimal(0),
        )
        row = {
            "run_id": self.cfg.run_id,
            "portfolio": "baseline",
            "captured_at": utc_now(),
            "equity": str(equity),
            "cash": str(account["cash"]),
            "gross_exposure": str(gross),
            "drawdown_pct": dd,
            "source": "alpaca-paper",
        }
        self.ledger.record_equity(row)
        return row
