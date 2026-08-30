from pathlib import Path

from veto.demo import decision_table, format_fills, format_orders, format_positions


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
    assert "paper_tape" in demo
    assert "sys.path.insert" in app
    assert "from veto.demo import render" in app


def test_paper_tape_formatters_are_newest_first():
    positions = format_positions(
        [{"symbol": "AAPL", "qty": 1, "avg_entry": 10, "current_price": 11, "asset_class": "us_equity"}]
    )
    assert positions[0]["symbol"] == "AAPL"
    orders = format_orders(
        [
            {"submitted_at": "1", "symbol": "OLD", "side": "buy", "status": "filled", "filled_qty": 1},
            {"submitted_at": "2", "symbol": "NEW", "side": "buy", "status": "filled", "filled_qty": 1},
        ],
        limit=20,
    )
    assert [row["symbol"] for row in orders] == ["NEW", "OLD"]
    fills = format_fills(
        [
            {"transaction_time": "1", "symbol": "OLD", "side": "buy", "qty": "1", "price": "10"},
            {"transaction_time": "2", "symbol": "NEW", "side": "buy", "qty": "1", "price": "11"},
        ]
    )
    assert [row["symbol"] for row in fills] == ["NEW", "OLD"]
