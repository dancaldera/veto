from __future__ import annotations

from pathlib import Path

import pytest

from veto.config import load_run_config
from veto.desk import RunSafetyError, VetoDesk
from veto.ledger import RunLedger


CONFIG = Path(__file__).resolve().parents[1] / "config" / "veto.yaml"


class FakeBroker:
    def __init__(self, *, equity=100_000.0, cash=100_000.0, positions=None, orders=None):
        self._equity = equity
        self._cash = cash
        self._positions = positions or []
        self._orders = orders or []

    def account(self):
        return {
            "id": "paper-id",
            "status": "ACTIVE",
            "equity": self._equity,
            "cash": self._cash,
            "buying_power": self._cash,
            "options_approved_level": 2,
            "account_number": "PA…",
        }

    def positions(self):
        return self._positions

    def all_orders(self, after=None):
        return self._orders


def test_init_rejects_wrong_equity(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "l.sqlite")
    try:
        with pytest.raises(RunSafetyError, match="Paper equity"):
            VetoDesk(cfg, ledger, FakeBroker(equity=10_000)).initialize()
        assert ledger.run(cfg.run_id) is None
    finally:
        ledger.close()


def test_init_rejects_order_history(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "l.sqlite")
    try:
        with pytest.raises(RunSafetyError, match="no order history"):
            VetoDesk(cfg, ledger, FakeBroker(orders=[{"id": "old"}])).initialize()
    finally:
        ledger.close()


def test_init_accepts_clean_hundred_k(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "l.sqlite")
    try:
        account = VetoDesk(cfg, ledger, FakeBroker()).initialize()
        assert account["equity"] == 100_000
        row = ledger.run(cfg.run_id)
        assert row["config_hash"] == cfg.fingerprint
        assert row["broker_account_id"] == "paper-id"
        snap = ledger.latest_equity(cfg.run_id)
        assert snap is not None
        assert float(snap["equity"]) == 100_000
        assert float(snap["drawdown_pct"]) == 0.0
    finally:
        ledger.close()


def test_paper_key_prefix_rejects_live_ak(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "AKFAKE")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")
    from veto.broker import BrokerError, _require_paper_keys

    with pytest.raises(BrokerError, match="live key"):
        _require_paper_keys()
