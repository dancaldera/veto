from pathlib import Path

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


def test_demo_and_entrypoint_cannot_place_orders():
    demo = (Path(__file__).resolve().parents[1] / "src" / "veto" / "demo.py").read_text()
    app = (Path(__file__).resolve().parents[1] / "streamlit_app.py").read_text()
    assert "There is no buy button" in demo
    assert 'st.button("Buy' not in demo
    assert "execute_pending" not in demo
    assert "check_stops" not in demo
    assert "no reconcile" in demo
    assert "sys.path.insert" in app
    assert "from veto.demo import render" in app
