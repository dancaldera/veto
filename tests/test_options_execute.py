from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from veto.broker import quantize_limit_price
from veto.config import load_run_config
from veto.desk import VetoDesk
from veto.ledger import RunLedger
from veto.options import OptionQuote, pick_collar


CONFIG = Path(__file__).resolve().parents[1] / "config" / "veto.yaml"


def _quotes(spot=100.0):
    exp = date.today() + timedelta(days=35)
    return [
        OptionQuote("P80", "put", spot * 0.80, exp, bid=1.0, ask=1.2, close=1.1),
        OptionQuote("P92", "put", spot * 0.92, exp, bid=2.0, ask=2.2, close=2.1),
        OptionQuote("P95", "put", spot * 0.95, exp, bid=3.0, ask=3.5, close=3.2),
        OptionQuote("C108", "call", spot * 1.08, exp, bid=1.5, ask=1.7, close=1.6),
        OptionQuote("C120", "call", spot * 1.20, exp, bid=0.4, ask=0.6, close=0.5),
    ]


def test_pick_collar_uses_8pct_strikes_and_dollar_debit():
    plan = pick_collar(_quotes(), 100.0, today=date.today())
    assert plan is not None
    assert plan.put.strike == 92
    assert plan.call.strike == 108
    # (2.2 ask put - 1.5 bid call) * 100
    assert abs(plan.estimated_debit - 70.0) < 0.01


def test_quantize_stock_and_crypto():
    assert quantize_limit_price(355.916, "stock") == 355.92
    assert quantize_limit_price(0.123456789, "crypto") == 0.12345679


class FakeBroker:
    def __init__(self, *, current=100.0, is_open=True):
        self.current = current
        self.is_open = is_open
        self.buys = []
        self.collars = []
        self.closed = []

    def latest_price(self, symbol, asset):
        return self.current

    def clock(self):
        return {"is_open": self.is_open}

    def buy_limit(self, symbol, notional, asset, limit_price, client_order_id):
        self.buys.append((symbol, limit_price, client_order_id))
        return {
            "id": "order-1",
            "status": "accepted",
            "submitted_at": "2026-08-29T00:00:00+00:00",
        }

    def submit_collar(self, plan, client_order_id):
        self.collars.append((plan.put.symbol, plan.call.symbol, client_order_id))
        return {
            "id": "collar-1",
            "status": "accepted",
            "submitted_at": "2026-08-29T00:00:00+00:00",
        }

    def option_quotes(self, symbol, **kwargs):
        return _quotes(kwargs.get("spot", self.current))

    def close(self, symbol):
        self.closed.append(symbol)
        return "close-1"


def _pending_buy(ledger, cfg, symbol="AAPL", asset="stock", price="100"):
    ledger.initialize_run(cfg, "test")
    return ledger.record_decision(
        {
            "run_id": cfg.run_id,
            "portfolio": "baseline",
            "symbol": symbol,
            "asset": asset,
            "strategy": cfg.strategy.name,
            "bar_end": "2026-08-28T00:00:00+00:00",
            "signal": "BUY",
            "signal_price": price,
            "notional": "625",
            "action": "buy_intent",
            "status": "pending",
            "config_hash": cfg.fingerprint,
        }
    )


def test_adverse_gap_expires_without_buying(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "l.sqlite")
    try:
        _pending_buy(ledger, cfg, price="100")
        broker = FakeBroker(current=103.0)
        out = VetoDesk(cfg, ledger, broker).execute_pending("stock")
        assert out[0]["action"] == "expired_gap"
        assert broker.buys == []
    finally:
        ledger.close()


def test_stock_limit_snaps_to_penny_and_submits_collar(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "l.sqlite")
    try:
        _pending_buy(ledger, cfg, symbol="MSFT", price="348.94")
        broker = FakeBroker(current=350.0)
        out = VetoDesk(cfg, ledger, broker).execute_pending("stock")
        assert out[0]["action"] == "submitted"
        assert broker.buys == [("MSFT", 355.92, f"veto-{out[0]['decision_id'][:12]}-buy")]
        assert out[0]["overlay"]["action"] == "collar_submitted"
        assert broker.collars
    finally:
        ledger.close()


def test_dry_run_does_not_submit(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "l.sqlite")
    try:
        _pending_buy(ledger, cfg)
        broker = FakeBroker()
        out = VetoDesk(cfg, ledger, broker).execute_pending("stock", dry_run=True)
        assert out[0]["action"] == "would_buy"
        assert broker.buys == []
        assert broker.collars == []
    finally:
        ledger.close()


def test_closed_market_defers_stock(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "l.sqlite")
    try:
        _pending_buy(ledger, cfg)
        broker = FakeBroker(is_open=False)
        out = VetoDesk(cfg, ledger, broker).execute_pending("stock")
        assert out == [{"action": "deferred_market_closed"}]
        assert broker.buys == []
    finally:
        ledger.close()


def test_halt_expires_pending_buy(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "l.sqlite")
    try:
        _pending_buy(ledger, cfg)
        ledger.halt(cfg.run_id, "drawdown")
        out = VetoDesk(cfg, ledger, FakeBroker()).execute_pending("stock")
        assert out[0]["action"] == "expired_halt"
    finally:
        ledger.close()


def test_overlay_skipped_when_premium_cap_hit(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "l.sqlite")
    try:
        _pending_buy(ledger, cfg)

        class RichQuotes(FakeBroker):
            def option_quotes(self, symbol, **kwargs):
                exp = date.today() + timedelta(days=35)
                # $20 debit per share = $2000 > $1500 cap
                return [
                    OptionQuote("P92", "put", 92, exp, bid=21.0, ask=22.0),
                    OptionQuote("C108", "call", 108, exp, bid=0.5, ask=0.6),
                ]

        broker = RichQuotes()
        out = VetoDesk(cfg, ledger, broker).execute_pending("stock")
        assert out[0]["action"] == "submitted"
        assert out[0]["overlay"]["action"] == "options_skipped"
        assert "premium_cap" in out[0]["overlay"]["reason"]
        assert broker.collars == []
    finally:
        ledger.close()
