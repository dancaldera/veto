# Hackathon build

Event: [Alpaca AI Trading Agents Hackathon](https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon), 28 August–4 September 2026.  
Judging (Alpaca): **P&L and creativity/engagement**.  
lablab also scores presentation, business value, application of technology, originality. Two extra prizes are social engagement.

This file is the spec. Keep it honest against the repo.

## Eligibility checklist

- [x] Dedicated Alpaca **paper** account, **$100,000** cash and equity, no leftover positions or orders
- [x] Options enabled on that paper account
- [x] Trading API **and** MCP or CLI (Veto will use all three)
- [x] Options in the live strategy (defined-risk overlay, not 0DTE directional)
- [x] One-page write-up: AI logic, risk gates, Alpaca infrastructure (`docs/one-pager.pdf`)
- [x] Public demo URL: [https://bszv8nabdvvipmbetdvtgv.streamlit.app/](https://bszv8nabdvvipmbetdvtgv.streamlit.app/)
- [x] PDF slides (`docs/slides.pdf`) and 16:9 cover (`docs/cover.png`)
- [ ] ≤4 min video (record from live demo + CLI; do not fake a fill)
- [x] Public GitHub
- [x] lablab team named **Veto**

## Architecture target

```text
closed daily bars (Alpaca)
        │
        ▼
fresh SMA 10/30  ──►  check_entry (frozen caps, ranked by cross strength)
        │                     │
        │                     ├─ reject → ledger reason (MCP can explain)
        │                     └─ allow
        ▼
stock: gap-capped share buy + 1-lot put/call overlay (~8% OTM, ~35 DTE)
crypto: gap-capped buy + 8% fill-derived poll stop
        │
        ▼
reconcile fills/fees → halt new buys on unknown order or qty mismatch
        │
        ├─ baseline (only arm that talks to Alpaca)
        ├─ shadow_regime
        └─ shadow_regime_news
        │
        ▼
MCP (read + gated preview)     Streamlit demo
```

The model talks to MCP. MCP talks to the desk. The desk is the only thing that may call the broker. Paper is hardcoded.

## Frozen numbers (do not tune mid-week)

- $100,000 start
- SMA 10 / 30, daily, fresh cross only
- $625 per cash-equity clip; max 8 names / $5,000; crypto 4 / $2,500; stock 6 / $3,750
- Correlation 0.80, 60 days, at most one match
- Stock gap 2%, crypto gap 3%
- Account drawdown halt 5%
- Options overlay: 1 put + 1 call, ~8% OTM, ~35 DTE, max debit **$1,500**, max **1** overlaid name
- If the overlay cannot be placed, keep the poll stop and log `options_skipped`

## MCP tools (no unconstrained buy)

| Tool | Side effect |
|---|---|
| `get_account` / `get_positions` / `get_halt_status` | read (halt reasons from reconcile / drawdown) |
| `latest_decisions` | read |
| `explain_decision(symbol)` | read |
| `preview_collar(symbol)` | read |
| `scan_now(dry_run=true)` | dry default |
| `execute_pending(asset, dry_run=true)` | dry default; live still through `check_entry` |

Server refuses to start unless paper mode is proven.

## Demo narrative (≤4 minutes)

1. Hook: the model asked to buy NVDA; Veto said no, with a ledger reason.
2. Scan table: signal / action / reason.
3. Collar preview + an Alpaca CLI or MCP call.
4. Reconcile / halt.
5. Paper-only disclaimer and this repo.

If the market prints no fresh SMA cross during the week, **do not fake one**. Show honest HOLDs, `preview_collar`, and the prior-research tape.

## Remaining before submit

1. Paste the demo URL on the lablab team page: https://bszv8nabdvvipmbetdvtgv.streamlit.app/
2. Record ≤4 min video from that demo + `veto scan --dry-run` + `preview-collar` + `veto reconcile`. Do not fake a fill. HOLD is allowed.
3. Paste [docs/lablab-copy.md](lablab-copy.md) on submit (tags: Alpaca, Alpaca MCP, Alpaca CLI, Python, Streamlit, FinBERT).

## Out of scope

- Copying the private lab source tree into this repo
- Live trading
- Letting the LLM pick symbols or change SMA windows
- Directional 0DTE “alpha” options
- Pitching $100k account return against a 50%-invested benchmark

## Success bar

Eligible: public repo, $100k paper, options in the strategy, MCP or CLI, video, slides, demo URL, one-pager.

Competitive: on camera, a request is **rejected with a ledger reason**, a stock candidate is **collared through Alpaca**, and nothing in MCP can bypass that.
