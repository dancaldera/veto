from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from veto.config import RunConfigError, load_run_config
from veto.desk import VetoDesk, rank_buy_candidates
from veto.ledger import RunLedger
from veto.risk import check_entry, check_overlay


CONFIG = Path(__file__).resolve().parents[1] / "config" / "veto.yaml"


def _cfg():
    return load_run_config(CONFIG)


def _buy_frame(last: float) -> pd.DataFrame:
    close = np.r_[np.full(40, 100.0), last]
    idx = pd.date_range("2026-01-01", periods=len(close), freq="D")
    return pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1.0},
        index=idx,
    )


def _ledger(tmp_path: Path, cfg):
    ledger = RunLedger(tmp_path / "ledger.sqlite")
    ledger.initialize_run(cfg, broker_account_id="test")
    return ledger


def test_manifest_loads_and_is_frozen():
    cfg = _cfg()
    assert cfg.run_id == "veto"
    assert cfg.starting_equity == 100_000
    assert cfg.options.max_names == 1
    assert len(cfg.fingerprint) == 64


def test_fingerprint_changes_when_yaml_changes(tmp_path):
    text = CONFIG.read_text().replace("max_premium: 1500", "max_premium: 1501")
    path = tmp_path / "broken.yaml"
    path.write_text(text)
    with pytest.raises(RunConfigError):
        load_run_config(path)


def test_ranking_is_by_strength_not_alphabet():
    cfg = _cfg()
    bars = {
        "AAPL": _buy_frame(120),
        "NVDA": _buy_frame(200),
        "MSFT": _buy_frame(150),
    }
    ranked = rank_buy_candidates(cfg, bars)
    assert [row[0] for row in ranked] == ["NVDA", "MSFT", "AAPL"]


def test_scan_records_buy_intents_in_strength_order(tmp_path):
    cfg = _cfg()
    ledger = _ledger(tmp_path, cfg)
    try:
        bars = {"AAPL": _buy_frame(120), "NVDA": _buy_frame(200)}
        rows = VetoDesk(cfg, ledger).scan(bars)
        baseline = [r for r in rows if r["portfolio"] == "baseline" and r["action"] == "buy_intent"]
        assert [r["symbol"] for r in baseline] == ["NVDA", "AAPL"]
        assert baseline[0]["rank"] == 0
    finally:
        ledger.close()


def test_dry_scan_does_not_write(tmp_path):
    cfg = _cfg()
    ledger = _ledger(tmp_path, cfg)
    try:
        VetoDesk(cfg, ledger).scan({"AAPL": _buy_frame(200)}, record=False)
        assert ledger.decisions(cfg.run_id) == []
    finally:
        ledger.close()


def test_halt_blocks_entry(tmp_path):
    cfg = _cfg()
    ledger = _ledger(tmp_path, cfg)
    try:
        ledger.halt(cfg.run_id, "test")
        result = check_entry(cfg, ledger, "baseline", "AAPL", "stock")
        assert result.allowed is False and result.reason == "run_halted"
    finally:
        ledger.close()


def test_overlay_cap_is_one_name(tmp_path):
    cfg = _cfg()
    ledger = _ledger(tmp_path, cfg)
    try:
        ledger.record_fill(
            {
                "fill_id": "put-1",
                "run_id": cfg.run_id,
                "portfolio": "baseline",
                "symbol": "AAPL",
                "asset": "option",
                "side": "buy",
                "qty": "1",
                "price": "4.00",
                "transaction_time": "2026-08-29T00:00:00+00:00",
            }
        )
        blocked = check_overlay(cfg, ledger, "baseline", "NVDA")
        assert blocked.allowed is False and blocked.reason == "overlay_max_names"
        over_budget = check_overlay(cfg, ledger, "baseline", "NVDA", estimated_debit=2000)
        assert "premium_cap" in over_budget.reason or over_budget.reason == "overlay_max_names"
        same = check_overlay(cfg, ledger, "baseline", "AAPL")
        assert same.reason == "overlay_already_open"
    finally:
        ledger.close()


def test_correlation_cap_rejects_third_clone(tmp_path):
    cfg = _cfg()
    ledger = _ledger(tmp_path, cfg)
    try:
        trend = _buy_frame(200)
        ledger.record_fill(
            {
                "fill_id": "a",
                "run_id": cfg.run_id,
                "portfolio": "baseline",
                "symbol": "AAPL",
                "asset": "stock",
                "side": "buy",
                "qty": "1",
                "price": "100",
                "transaction_time": "2026-08-01T00:00:00+00:00",
            }
        )
        ledger.record_fill(
            {
                "fill_id": "b",
                "run_id": cfg.run_id,
                "portfolio": "baseline",
                "symbol": "MSFT",
                "asset": "stock",
                "side": "buy",
                "qty": "1",
                "price": "100",
                "transaction_time": "2026-08-01T00:00:00+00:00",
            }
        )
        bars = {"AAPL": trend, "MSFT": trend * 1.1, "NVDA": trend * 1.2}
        result = check_entry(cfg, ledger, "baseline", "NVDA", "stock", bars)
        assert result.allowed is False
        assert result.reason.startswith("correlation_cap")
    finally:
        ledger.close()
