# Veto

**The model may research. Veto decides.**

Veto is a fail-closed **Alpaca paper** trading agent for the [Alpaca AI Trading Agents Hackathon](https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon) (28 August–4 September 2026).

It is the opposite of “paste a ticker into a chat and send a market order.” Frozen rules size every order. An LLM can inspect, explain, and preview through Alpaca MCP — it cannot authorize a fill. Stock entries carry a defined-risk **options overlay**. Crypto keeps an 8% fill-derived stop. Regime and news models run as **shadows** that never touch the broker.

Paper trading is simulated. It is not live performance and not a prediction.

## Status

This repository starts as **prior research + the hackathon spec**. Implementation lands in later commits during the event window. There is no trading code in the initial commit on purpose.

| Document | What it is |
|---|---|
| [docs/prior-research.md](docs/prior-research.md) | Private lab I ran before this hackathon: frozen SMA 10/30, $100k paper desk, 2022–2026 Alpaca replay |
| [docs/hackathon.md](docs/hackathon.md) | Eligibility, architecture, and what gets built this week |

## The bet

A 2022-01-01 → 2026-08-29 replay of the frozen SMA book on Alpaca daily bars returned **+5.4%** at the $100k account level against a **+59%** 25% stocks / 25% crypto / 50% cash benchmark. Win rate **29%**. **47%** of exits were 8% poll stops, not reverse crosses.

Veto does not try to “pick better tickers” in seven days. It tries to stop a poll and a language model from pretending to be a risk desk: resting options for defined loss, a ledger that can halt, and an MCP surface that cannot bypass the gates.

## Hard rules

- Alpaca **paper** endpoint only. No live-trading code path.
- Competition account starts at **$100,000**, empty of positions and order history.
- Baseline is the only arm that may submit broker orders.
- Shadows (regime, FinBERT news) cannot place orders.
- MCP tools are read / dry-run / explain. There is no unconstrained `buy(symbol, qty)`.

## License

MIT. See [LICENSE](LICENSE).
