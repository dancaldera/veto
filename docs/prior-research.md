# Prior research: a frozen paper desk (2022–2026)

This note is **research I ran before this hackathon**, not code in this repository. Veto is the public, from-scratch agent that follows from it.

Paper results are simulated. They are not live trading performance and not a forecast.

## Question

Does a frozen, long-only SMA 10/30 paper desk survive costs, gaps, and an 8% protective stop well enough to beat a lazy mix of the same assets — and is “let a model pick the ticker” the right next layer?

## Setup (frozen; not tuned against this replay)

- Starting cash and equity: **$100,000**. No margin.
- Signal: **fresh** SMA(10) × SMA(30) cross on the **last closed daily bar**. Reverse cross exits. Long only.
- Watchlist: 8 crypto pairs (BTC, ETH, SOL, LTC, LINK, DOGE, AVAX, AAVE vs USD) and 9 US names (AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AMD, NFLX).
- Size: **$625** per entry. At most 8 names / **$5,000** gross. Crypto cap 4 / $2,500. Stock cap 6 / $3,750.
- Correlation: reject a candidate at **0.80** or above with more than one holding (60 daily returns).
- Stop: **8%** from fill-derived average entry, polled rather than resting at the broker.
- Adverse gap: skip if the next open is more than **2%** (stocks) or **3%** (crypto) past the signal close.
- Kill switch: halt **new buys** at **5%** high-water account drawdown. Exits stay on.
- Data: Alpaca daily bars (IEX equities, Alpaca US spot crypto), 2022-01-01 through 2026-08-29.
- Costs in the replay: 5 bps equity slippage, 25 bps crypto taker.
- Research arms that **could not order**: a 0–4 regime score (min 3) and a FinBERT negative-news robust z-score. Baseline only reached the broker.

## Account-level result

Synchronized portfolio replay of that exact spec:

| | Frozen SMA desk | 25% stocks / 25% crypto / 50% cash, monthly rebalance |
|---|---|---|
| Account return | **+5.38%** ($100k → $105.4k) | **+59.1%** |
| Max drawdown | −2.38% | −35.4% |
| Completed trades | 238 | — |
| Win rate | 29.4% | — |
| Expectancy | +$19.51 / completed trade | — |
| Profit factor | 1.66 | — |

Tape shape: 112 of 238 sells (**47%**) were 8% stops; 126 were reverse-cross. Median trade **−$35**, mean **+$19**. Seven entries died on the gap cap. Same-day crosses were filled **alphabetically**, so AAVE/AAPL/AMD ate slots before NVDA.

Unconstrained buy-and-hold on the same names over the window was wildly unequal (NVDA +624%, AMD +210%, BTC +64%, AVAX −94%). A 5% invested SMA book cannot look like those numbers at the account level. Low drawdown here is mostly “almost no money at risk,” not proven skill.

## What that taught me

1. **SMA 10/30 is a valid experiment, not a competitive edge.** 29% win rate is normal for trend-following. The account-level gap vs the 50%-invested benchmark is almost guaranteed when only $5k of $100k is deployed.
2. **An 8% poll stop fights the SMA.** Trend-following wants to eat noise. Nearly half the exits were stops, then a fresh cross was required to re-enter, so shakeouts missed the rest of the move. Between 30-minute polls — and overnight for stocks — the fill can be much worse than 8%.
3. **$625 clips cannot wear a 100-share options contract.** A real collar on mega-cap names needs either a larger lot or a **separate 1-contract overlay** with a premium cap. The lab never traded options. That is the eligibility hole Veto has to close honestly, not by pretending a 2-share AAPL clip is collared.
4. **The model is the wrong authorization layer.** Regime and news were useful as *shadows* (they can never submit). Letting an LLM size or send the order would have destroyed the only original property of the desk: a frozen manifest plus a ledger that can halt.
5. **Shadows that do not get the same stop as baseline are not comparable.** Live stop checks walked baseline only. A hackathon demo that “proves” news-gating would be lying unless shadows share the stop/option economics.
6. **Alphabetical allocation is a hidden policy.** First-come in the alphabet is not a ranking. Same-day crosses should sort by trend strength.

## What I am not claiming

- That SMA 10/30 will make money next week.
- That the +5.4% replay is an edge after multiple-testing and fees on a fully invested book.
- That FinBERT or the regime score should be promoted off a few weeks of paper.

## What Veto takes from this

Keep the frozen signal and the risk gates. Do not let the LLM pick symbols or bypass `check_entry`. Replace the equity poll stop with a **defined-risk options overlay** (long ~8% OTM put, short ~8% OTM call, ~35 DTE, premium cap). Rank same-day crosses. Put explain/preview on MCP. Keep shadows off the broker. Paper endpoint hardcoded.

The research question for the hackathon week is no longer “does SMA win?” It is: **can an agent on Alpaca be useful because it knows how to refuse?**
