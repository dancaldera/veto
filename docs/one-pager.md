# Veto — one page

**The model may research. Veto decides.**  
Alpaca AI Trading Agents Hackathon · paper trading only · [github.com/dancaldera/veto](https://github.com/dancaldera/veto) · [demo](https://bszv8nabdvvipmbetdvtgv.streamlit.app/)

Veto is a fail-closed **Alpaca paper** desk. An LLM can inspect, explain, and preview. It cannot size or send an order. Frozen rules authorize every fill. Stock entries carry a defined-risk **options overlay**. Crypto keeps an 8% fill-derived poll stop. Shadows never touch the broker.

## AI logic

The language model is not the authorization layer. Closed daily bars produce a **fresh SMA 10/30** signal. Same-day buys are ranked by cross strength, not alphabet. `check_entry` is the only path to a buy intent. MCP tools are read, explain, collar preview, and **dry-run** scan/execute. There is no `buy(symbol, qty)`.

Regime and FinBERT news arms are **declared shadows** (`shadow_regime`, `shadow_regime_news`). They are not live this week; shipping a fake news model would be a lie. When they run, they still cannot call `buy_limit` or `submit_collar`.

## Risk gates (frozen)

| Gate | Rule |
|---|---|
| Account | $100,000 start, no margin, paper endpoint hardcoded |
| Clip | $625; max 8 names / $5,000; crypto 4 / $2,500; stock 6 / $3,750 |
| Correlation | reject at ≥0.80 with more than one holding (60d) |
| Gap | skip if live price is >2% (stock) or >3% (crypto) past the signal close |
| Stop | 8% from **ledger** average entry, polled — not a resting broker stop |
| Overlay | 1-lot put/call, ~8% OTM, ~35 DTE, max debit $1,500, max 1 name. If the collar is live, skip the poll flatten. If it cannot be placed, keep the poll stop and log `options_skipped` |
| Halt | unknown broker order, qty mismatch vs the fill ledger, or **5%** high-water account drawdown. New buys stop. Exits stay on |

## Alpaca surface

- **Trading API** — gap-capped limit buys, MLEG collar, closes. `paper=True` is not a flag.
- **MCP** — `get_account`, `get_positions`, `get_halt_status` (real halt reasons), `latest_decisions`, `explain_decision`, `preview_collar`, `scan_now` / `execute_pending` default `dry_run=true`.
- **CLI** — `veto scan`, `execute`, `preview-collar` (prints the Alpaca CLI string), `reconcile`, `stops`.

## Paper-only

Keys must be `PK…`. Live `AK…` keys are rejected. Competition account is $100k, empty at init. Paper P&L is simulated. It is not live performance and not a forecast.

## Prior research (not this week’s P&L)

A 2022-01-01 → 2026-08-29 replay of this frozen SMA book returned **+5.4%** at the $100k account vs **+59%** for a 25% stocks / 25% crypto / 50% cash benchmark. Win rate 29%. 47% of exits were 8% poll stops. See [docs/prior-research.md](prior-research.md). Veto does not pitch that tape as an edge. It pitches a desk that knows how to **refuse**.
