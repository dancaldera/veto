from __future__ import annotations

from pathlib import Path

from veto.config import load_run_config
from veto.desk import VetoDesk
from veto.ledger import RunLedger
from veto.risk import check_entry, drawdown_pct


CONFIG = Path(__file__).resolve().parents[1] / "config" / "veto.yaml"


class FakeBroker:
    def __init__(
        self,
        *,
        equity=100_000.0,
        cash=100_000.0,
        fills=None,
        fees=None,
        orders=None,
        positions=None,
    ):
        self._equity = equity
        self._cash = cash
        self._fills = fills or []
        self._fees = fees or []
        self._orders = orders or []
        self._positions = positions or []
        self.closed = []

    def account(self):
        return {
            "id": "paper-id",
            "status": "ACTIVE",
            "equity": self._equity,
            "cash": self._cash,
            "buying_power": self._cash,
            "options_approved_level": 3,
            "account_number": "PA…",
        }

    def positions(self):
        return self._positions

    def all_orders(self, after=None):
        return self._orders

    def activities(self, kind, after=None):
        if kind == "FILL":
            return self._fills
        if kind in {"CFEE", "FEE"}:
            return self._fees
        return []

    def close(self, symbol):
        self.closed.append(symbol)
        return "close-1"


def _cfg():
    return load_run_config(CONFIG)


def _desk(tmp_path):
    cfg = _cfg()
    ledger = RunLedger(tmp_path / "ledger.sqlite")
    broker = FakeBroker()
    desk = VetoDesk(cfg, ledger, broker)
    desk.initialize()
    return cfg, ledger, desk, broker


def _submitted_buy(ledger, cfg, *, broker_order_id="order-1", qty="6.25", price="100"):
    decision_id = ledger.record_decision(
        {
            "run_id": cfg.run_id,
            "portfolio": "baseline",
            "symbol": "AAPL",
            "asset": "stock",
            "strategy": cfg.strategy.name,
            "bar_end": "2026-08-28T00:00:00+00:00",
            "signal": "BUY",
            "signal_price": "100",
            "notional": "625",
            "action": "buy_intent",
            "status": "submitted",
            "config_hash": cfg.fingerprint,
        }
    )
    ledger.record_order(
        {
            "run_id": cfg.run_id,
            "decision_id": decision_id,
            "portfolio": "baseline",
            "client_order_id": "client-1",
            "broker_order_id": broker_order_id,
            "symbol": "AAPL",
            "asset": "stock",
            "side": "buy",
            "status": "accepted",
        }
    )
    return decision_id, qty, price


def test_drawdown_pct_is_high_water_relative():
    assert drawdown_pct(95_000, 100_000) == 5.0
    assert drawdown_pct(100_000, 100_000) == 0.0
    assert drawdown_pct(110_000, 100_000) == 0.0


def test_matching_fill_does_not_halt(tmp_path):
    cfg, ledger, desk, broker = _desk(tmp_path)
    try:
        decision_id, *_ = _submitted_buy(ledger, cfg)
        broker._equity = 100_010
        broker._cash = 99_375
        broker._fills = [
            {
                "id": "fill-1",
                "order_id": "order-1",
                "symbol": "AAPL",
                "side": "buy",
                "qty": "6.25",
                "price": "100",
                "transaction_time": "2026-08-29T14:00:00Z",
            }
        ]
        broker._orders = [{"id": "order-1", "status": "filled", "filled_qty": 6.25}]
        broker._positions = [
            {"symbol": "AAPL", "qty": 6.25, "current_price": 100.0, "asset_class": "us_equity"}
        ]
        result = desk.reconcile()
        assert result["halted"] is False
        assert result["new_fills"] == 1
        assert result["unknown_orders"] == []
        assert result["quantity_mismatches"] == []
        assert ledger.decisions(cfg.run_id)[0]["status"] == "filled"
        assert ledger.decisions(cfg.run_id)[0]["decision_id"] == decision_id
        halt = desk.halt_status()
        assert halt["halted"] is False
        assert halt["halt_reason"] is None
    finally:
        ledger.close()


def test_unknown_fill_halts_new_buys(tmp_path):
    cfg, ledger, desk, broker = _desk(tmp_path)
    try:
        broker._fills = [
            {
                "id": "rogue-fill",
                "order_id": "not-ours",
                "symbol": "NVDA",
                "side": "buy",
                "qty": "1",
                "price": "100",
                "transaction_time": "2026-08-29T14:00:00Z",
            }
        ]
        broker._orders = [{"id": "not-ours", "status": "filled", "filled_qty": 1}]
        broker._positions = [
            {"symbol": "NVDA", "qty": 1, "current_price": 100.0, "asset_class": "us_equity"}
        ]
        result = desk.reconcile()
        assert result["halted"] is True
        assert "not-ours" in result["unknown_orders"]
        assert result["halt_reason"].startswith("reconciliation_failed")
        blocked = check_entry(cfg, ledger, "baseline", "AAPL", "stock")
        assert blocked.allowed is False and blocked.reason == "run_halted"
        halt = desk.halt_status()
        assert halt["halted"] is True
        assert "unknown_orders" in halt["halt_reason"]
    finally:
        ledger.close()


def test_qty_mismatch_halts(tmp_path):
    cfg, ledger, desk, broker = _desk(tmp_path)
    try:
        _submitted_buy(ledger, cfg)
        broker._fills = [
            {
                "id": "fill-1",
                "order_id": "order-1",
                "symbol": "AAPL",
                "side": "buy",
                "qty": "6.25",
                "price": "100",
                "transaction_time": "2026-08-29T14:00:00Z",
            }
        ]
        broker._orders = [{"id": "order-1", "status": "filled", "filled_qty": 6.25}]
        broker._positions = [
            {"symbol": "AAPL", "qty": 99, "current_price": 100.0, "asset_class": "us_equity"}
        ]
        result = desk.reconcile()
        assert result["halted"] is True
        assert "AAPL" in result["quantity_mismatches"]
    finally:
        ledger.close()


def test_option_broker_position_is_not_a_qty_mismatch(tmp_path):
    cfg, ledger, desk, broker = _desk(tmp_path)
    try:
        _submitted_buy(ledger, cfg)
        broker._fills = [
            {
                "id": "fill-1",
                "order_id": "order-1",
                "symbol": "AAPL",
                "side": "buy",
                "qty": "6.25",
                "price": "100",
                "transaction_time": "2026-08-29T14:00:00Z",
            }
        ]
        broker._orders = [{"id": "order-1", "status": "filled", "filled_qty": 6.25}]
        broker._positions = [
            {"symbol": "AAPL", "qty": 6.25, "current_price": 100.0, "asset_class": "us_equity"},
            {
                "symbol": "AAPL260918P00180000",
                "qty": 1,
                "current_price": 4.0,
                "asset_class": "us_option",
            },
        ]
        result = desk.reconcile()
        assert result["halted"] is False
        assert result["quantity_mismatches"] == []
    finally:
        ledger.close()


def test_stop_uses_fill_derived_entry_not_broker_cost_basis(tmp_path):
    cfg, ledger, desk, broker = _desk(tmp_path)
    try:
        broker._positions = [
            {"symbol": "AAPL", "qty": 6.25, "avg_entry": 0, "current_price": 91.9}
        ]
        ledger.record_fill(
            {
                "fill_id": "a",
                "run_id": cfg.run_id,
                "portfolio": "baseline",
                "symbol": "AAPL",
                "asset": "stock",
                "side": "buy",
                "qty": "6.25",
                "price": "100",
                "transaction_time": "2026-08-01T00:00:00+00:00",
            }
        )
        out = desk.check_stops()
        assert out[0]["action"] == "stopped"
        assert broker.closed == ["AAPL"]
    finally:
        ledger.close()


def test_stop_skipped_when_collar_is_live(tmp_path):
    cfg, ledger, desk, broker = _desk(tmp_path)
    try:
        broker._positions = [
            {"symbol": "AAPL", "qty": 6.25, "avg_entry": 0, "current_price": 91.9}
        ]
        ledger.record_fill(
            {
                "fill_id": "a",
                "run_id": cfg.run_id,
                "portfolio": "baseline",
                "symbol": "AAPL",
                "asset": "stock",
                "side": "buy",
                "qty": "6.25",
                "price": "100",
                "transaction_time": "2026-08-01T00:00:00+00:00",
            }
        )
        ledger.record_decision(
            {
                "run_id": cfg.run_id,
                "portfolio": "baseline",
                "symbol": "AAPL",
                "asset": "option",
                "strategy": "collar",
                "bar_end": "2026-08-01T00:00:00+00:00",
                "signal": "COLLAR",
                "signal_price": "100",
                "notional": "70",
                "action": "collar_open",
                "status": "submitted",
                "config_hash": cfg.fingerprint,
            }
        )
        out = desk.check_stops()
        assert out[0]["action"] == "none"
        assert out[0]["reason"] == "collar_live"
        assert broker.closed == []
    finally:
        ledger.close()


def test_stop_dry_run_does_not_close(tmp_path):
    cfg, ledger, desk, broker = _desk(tmp_path)
    try:
        broker._positions = [
            {"symbol": "BTCUSD", "qty": 0.01, "avg_entry": 0, "current_price": 90_000}
        ]
        ledger.record_fill(
            {
                "fill_id": "btc",
                "run_id": cfg.run_id,
                "portfolio": "baseline",
                "symbol": "BTC/USD",
                "asset": "crypto",
                "side": "buy",
                "qty": "0.01",
                "price": "100000",
                "transaction_time": "2026-08-01T00:00:00+00:00",
            }
        )
        out = desk.check_stops(dry_run=True)
        assert out[0]["action"] == "would_stop"
        assert broker.closed == []
    finally:
        ledger.close()


def test_drawdown_halt_at_five_percent(tmp_path):
    cfg, ledger, desk, broker = _desk(tmp_path)
    try:
        broker._equity = 94_000
        broker._cash = 94_000
        result = desk.reconcile()
        assert result["halted"] is True
        assert result["drawdown_pct"] == 6.0
        assert result["halt_reason"].startswith("drawdown_halt")
        blocked = check_entry(cfg, ledger, "baseline", "AAPL", "stock")
        assert blocked.reason == "run_halted"
    finally:
        ledger.close()


def test_drawdown_under_five_percent_does_not_halt(tmp_path):
    cfg, ledger, desk, broker = _desk(tmp_path)
    try:
        broker._equity = 96_000
        broker._cash = 96_000
        result = desk.reconcile()
        assert result["halted"] is False
        assert result["drawdown_pct"] == 4.0
        assert check_entry(cfg, ledger, "baseline", "AAPL", "stock").allowed is True
    finally:
        ledger.close()
