from veto.demo import decision_table


def test_decision_table_keeps_baseline_reasons():
    rows = [
        {"portfolio": "baseline", "symbol": "NVDA", "asset": "stock", "signal": "BUY", "action": "none", "reason": "correlation_cap:2"},
        {"portfolio": "shadow_regime", "symbol": "NVDA", "asset": "stock", "signal": "BUY", "action": "none", "reason": "missing_regime"},
        {"portfolio": "baseline", "symbol": "AAPL", "asset": "stock", "signal": "HOLD", "action": "none", "reason": "no_fresh_cross"},
    ]
    table = decision_table(rows)
    assert [r["symbol"] for r in table] == ["NVDA", "AAPL"]
    assert table[0]["reason"] == "correlation_cap:2"
