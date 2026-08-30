from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from veto.bars import drop_forming_bar
from veto.config import load_run_config
from veto.desk import VetoDesk
from veto.ledger import RunLedger


CONFIG = Path(__file__).resolve().parents[1] / "config" / "veto.yaml"


def _frame(days, last="2026-08-29"):
    idx = pd.date_range(end=last, periods=days, freq="D")
    close = pd.Series(range(100, 100 + days), dtype=float)
    return pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1.0},
        index=idx,
    )


def test_drop_forming_bar_removes_today_utc():
    df = _frame(5, last="2026-08-29")
    now = datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)
    out = drop_forming_bar(df, "1d", now=now)
    assert out.index[-1] == pd.Timestamp("2026-08-28")


def test_drop_forming_bar_keeps_closed_yesterday():
    df = _frame(5, last="2026-08-28")
    now = datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)
    out = drop_forming_bar(df, "1d", now=now)
    assert len(out) == 5


def test_dry_scan_does_not_require_init(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "fresh.sqlite")
    try:
        close = [100.0] * 41 + [200.0]
        idx = pd.date_range("2026-01-01", periods=len(close), freq="D")
        frame = pd.DataFrame(
            {"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1.0},
            index=idx,
        )
        rows = VetoDesk(cfg, ledger).scan({"AAPL": frame}, record=False)
        assert any(r.get("signal") == "BUY" for r in rows)
        assert ledger.run(cfg.run_id) is None
    finally:
        ledger.close()


def test_explain_decision_reads_ledger_reason(tmp_path):
    cfg = load_run_config(CONFIG)
    ledger = RunLedger(tmp_path / "l.sqlite")
    try:
        ledger.initialize_run(cfg, "test")
        ledger.record_decision(
            {
                "run_id": cfg.run_id,
                "portfolio": "baseline",
                "symbol": "NVDA",
                "asset": "stock",
                "strategy": cfg.strategy.name,
                "bar_end": "2026-08-28T00:00:00+00:00",
                "signal": "BUY",
                "signal_price": "100",
                "notional": "625",
                "action": "none",
                "reason": "correlation_cap:2",
                "status": "recorded",
                "config_hash": cfg.fingerprint,
            }
        )
        info = VetoDesk(cfg, ledger).explain_decision("NVDA")
        assert info["reason"] == "correlation_cap:2"
        assert info["halted"] is False
    finally:
        ledger.close()
