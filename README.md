# Veto

**The model may research. Veto decides.**

Veto is a fail-closed **Alpaca paper** trading agent for the [Alpaca AI Trading Agents Hackathon](https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon) (28 August–4 September 2026).

It is the opposite of “paste a ticker into a chat and send a market order.” Frozen rules size every order. An LLM can inspect, explain, and preview through Alpaca MCP — it cannot authorize a fill. Stock entries carry a defined-risk **options overlay**. Crypto keeps an 8% fill-derived stop. Regime and FinBERT news arms are **declared shadows** that never touch the broker; they are not live this week.

Paper trading is simulated. It is not live performance and not a prediction.

## Status

Fail-closed loop is in: frozen manifest, SMA 10/30, ranked scan, gap-capped execute, 1-lot collar overlay, **reconcile**, **8% poll stops** (skipped when a collar is live), **5% drawdown halt**. Paper `init` is bound to a clean $100k Alpaca account.

**Live demo (paper only, no buy button):** [bszv8nabdvvipmbetdvtgv.streamlit.app](https://bszv8nabdvvipmbetdvtgv.streamlit.app/)

| Document | What it is |
|---|---|
| [docs/one-pager.md](docs/one-pager.md) / [docs/one-pager.pdf](docs/one-pager.pdf) | One-page write-up Alpaca asked for |
| [docs/slides.pdf](docs/slides.pdf) | 8-slide pitch |
| [docs/cover.png](docs/cover.png) | 16:9 cover |
| [docs/prior-research.md](docs/prior-research.md) | Private lab I ran before this hackathon: frozen SMA 10/30, $100k paper desk, 2022–2026 Alpaca replay |
| [docs/hackathon.md](docs/hackathon.md) | Eligibility, architecture, and remaining submit steps |
| [docs/lablab-copy.md](docs/lablab-copy.md) | Form paste (after the video) |
| [docs/schedule.md](docs/schedule.md) | Paper-only cron/systemd loop (fake money) |

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,broker]'
pytest -q
veto fingerprint          # frozen manifest hash
veto status               # paper equity/cash (needs .env, never committed)
veto init                 # bind ledger to a clean $100k paper account
veto init --offline       # local ledger only; does not talk to Alpaca
veto preview-collar AAPL  # 1-lot put/call overlay, no order
veto scan --dry-run       # closed daily bars; does not write the ledger
veto explain NVDA         # latest baseline reason (the veto)
veto execute --asset stock --dry-run
veto reconcile            # import paper fills/fees; halt on unknown order or qty mismatch
veto stops --dry-run      # 8% fill-derived poll; skips names with a live collar
python -m veto.mcp_server # MCP: inspect/explain/preview; scan/execute default dry-run
pip install -e '.[demo,broker]'
veto demo                 # Streamlit inspect/preview app — no buy button
DRY_RUN=1 bash scripts/daily_paper_run.sh   # scheduled loop preview (paper only)
```

The demo is `streamlit_app.py`. Hosted: [https://bszv8nabdvvipmbetdvtgv.streamlit.app/](https://bszv8nabdvvipmbetdvtgv.streamlit.app/). Paper secrets on Streamlit Cloud. The app never places orders.

## The bet

A 2022-01-01 → 2026-08-29 replay of the frozen SMA book on Alpaca daily bars returned **+5.4%** at the $100k account level against a **+59%** 25% stocks / 25% crypto / 50% cash benchmark. Win rate **29%**. **47%** of exits were 8% poll stops, not reverse crosses.

Veto does not try to “pick better tickers” in seven days. It tries to stop a poll and a language model from pretending to be a risk desk: resting options for defined loss, a ledger that can halt, and an MCP surface that cannot bypass the gates.

## Hard rules

- Alpaca **paper** endpoint only. No live-trading code path. Keys must be `PK…`; `AK…` is rejected.
- Competition account starts at **$100,000**, empty of positions and order history.
- Baseline is the only arm that may submit broker orders (paper fills, fake money).
- Shadows (regime, FinBERT news) cannot place orders.
- MCP tools are read / dry-run / explain. There is no unconstrained `buy(symbol, qty)`.

## License

MIT. See [LICENSE](LICENSE).
