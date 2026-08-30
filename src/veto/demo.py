"""Streamlit demo. Inspect and preview only — no order buttons."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .cli import DEFAULT_CONFIG, DEFAULT_LEDGER
from .config import load_run_config
from .desk import VetoDesk
from .ledger import LedgerError, RunLedger
from .risk import drawdown_pct

REPO = Path(__file__).resolve().parents[2]


def apply_streamlit_secrets() -> None:
    """Copy Streamlit Cloud secrets into env without logging values."""
    try:
        import streamlit as st

        secrets = st.secrets
    except Exception:
        return
    for name in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
        try:
            value = secrets[name]
        except Exception:
            continue
        if value and not os.getenv(name):
            os.environ[name] = str(value)


def load_ledger(cfg) -> RunLedger:
    if DEFAULT_LEDGER.exists():
        ledger = RunLedger(DEFAULT_LEDGER)
        try:
            ledger.assert_manifest(cfg)
            return ledger
        except LedgerError:
            ledger.close()
    ledger = RunLedger(":memory:")
    ledger.initialize_run(cfg, "demo")
    return ledger


def account_snapshot(broker) -> dict[str, Any] | None:
    if broker is None:
        return None
    try:
        acct = broker.account()
        acct["positions"] = broker.positions()
        return acct
    except Exception as exc:
        return {"error": str(exc)}


def decision_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = [r for r in rows if r.get("portfolio") == "baseline"]
    return [
        {
            "symbol": r.get("symbol"),
            "asset": r.get("asset"),
            "signal": r.get("signal"),
            "action": r.get("action"),
            "reason": r.get("reason"),
        }
        for r in baseline
    ]


def render() -> None:
    import streamlit as st

    apply_streamlit_secrets()
    st.set_page_config(page_title="Veto", layout="wide")
    st.title("Veto")
    st.caption("The model may research. Veto decides. Paper trading only — not live performance.")

    cfg = load_run_config(DEFAULT_CONFIG)
    ledger = load_ledger(cfg)

    broker = None
    broker_error = None
    try:
        from .broker import PaperBroker

        broker = PaperBroker()
    except Exception as exc:
        broker_error = str(exc)

    desk = VetoDesk(cfg, ledger, broker)

    col1, col2, col3, col4, col5 = st.columns(5)
    acct = account_snapshot(broker)
    halt = None
    try:
        halt = desk.halt_status()
    except Exception:
        halt = {"halted": False, "status": "uninitialized", "halt_reason": None}

    if acct and "error" not in acct:
        col1.metric("Equity", f"${acct['equity']:,.0f}")
        col2.metric("Cash", f"${acct['cash']:,.0f}")
        col3.metric("Options level", acct.get("options_approved_level", "—"))
    else:
        col1.metric("Equity", "—")
        col2.metric("Cash", "—")
        col3.metric("Options level", "—")
    col4.metric("Halt", "YES" if halt and halt.get("halted") else "no")
    dd = halt.get("drawdown_pct") if halt else None
    if dd is None and acct and "error" not in acct:
        dd = drawdown_pct(float(acct["equity"]), cfg.starting_equity)
    col5.metric("Drawdown", f"{dd:.2f}%" if dd is not None else "—")

    if broker_error:
        st.info(f"Paper broker offline: {broker_error}")
    if acct and acct.get("error"):
        st.warning(acct["error"])
    if halt and halt.get("halt_reason"):
        st.error(f"Halt reason: {halt['halt_reason']}")

    st.subheader("Last scan (closed bars)")
    st.write(
        "Dry run only. This does not write the ledger or place orders. "
        "HOLD is an allowed tape — Veto will not invent a fresh SMA cross."
    )
    if st.button("Run dry scan"):
        from .bars import fetch_watchlist

        with st.spinner("Fetching closed daily bars…"):
            bars = fetch_watchlist(cfg)
            rows = desk.scan(bars, record=False)
        st.session_state["scan_rows"] = decision_table(rows)

    table = st.session_state.get("scan_rows")
    if table:
        st.dataframe(table, width="stretch", hide_index=True)
        buys = [r for r in table if r["action"] == "buy_intent"]
        st.caption(f"{len(buys)} buy intent(s). Reasons on HOLD/reject rows are the veto.")
    else:
        st.caption("No scan in this session yet.")

    left, right = st.columns(2)
    stocks = list(cfg.stock_symbols)
    with left:
        st.subheader("Explain a decision")
        symbol = st.selectbox("Symbol", stocks + list(cfg.crypto_symbols), index=0)
        if st.button("Explain"):
            st.json(desk.explain_decision(symbol))
    with right:
        st.subheader("Collar preview")
        stock = st.selectbox("Underlying", stocks, index=0, key="collar_symbol")
        if st.button("Preview collar"):
            if broker is None:
                st.warning("Paper keys required for a live collar preview.")
            else:
                with st.spinner("Loading option chain…"):
                    preview = desk.preview_collar(stock)
                st.json(preview)
                if preview.get("cli"):
                    st.caption("Alpaca CLI string (not executed):")
                    st.code(preview["cli"], language="bash")

    with st.expander("Halt status (read-only)"):
        st.json(halt)

    st.divider()
    st.markdown(
        """
**This demo cannot place orders.** There is no buy button, no execute, and no reconcile.
MCP tools default to dry-run. Paper results are simulated and are not a prediction.

[GitHub](https://github.com/dancaldera/veto) · [one-pager](https://github.com/dancaldera/veto/blob/main/docs/one-pager.md) · frozen SMA 10/30 · $625 clips · 8% collar overlay
"""
    )
    ledger.close()
