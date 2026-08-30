# lablab form copy

Paste on submit after the video exists. Demo URL is live.

**Title:** Veto — the model may research. Veto decides.

**Short description:** Fail-closed Alpaca paper desk. An LLM can inspect, explain, and preview a collar. Frozen rules size every order. There is no buy button.

**Long description:**

Veto is the opposite of paste-a-ticker-into-chat. Closed daily bars produce a fresh SMA 10/30 signal. Same-day buys are ranked by cross strength. `check_entry` enforces frozen caps ($625 clips, 8 names, correlation, gap). Stock entries overlay a 1-lot put/call collar (~8% OTM, ~35 DTE). Crypto keeps an 8% fill-derived poll stop. Reconcile imports paper fills and halts new buys on an unknown broker order, a quantity mismatch, or a 5% high-water drawdown. Exits stay on.

The model talks to Alpaca MCP. MCP talks to the desk. The desk is the only thing that may call the broker. Tools are read, explain, preview, and dry-run scan/execute. There is no `buy(symbol, qty)`. Shadows (regime, FinBERT) are declared and cannot order.

Paper trading is simulated. A prior 2022–2026 replay of this frozen book returned +5.4% at the $100k account against a +59% 25/25/50 benchmark. Veto does not pitch that as an edge. It pitches a desk that knows how to refuse.

Repo: https://github.com/dancaldera/veto  
Demo: https://bszv8nabdvvipmbetdvtgv.streamlit.app/

**Tags:** Alpaca, Alpaca MCP, Alpaca CLI, Python, Streamlit, FinBERT
