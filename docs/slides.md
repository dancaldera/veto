# Veto — 8 slides

Speaker notes for `docs/slides.pdf`. Do not fake an SMA cross on camera.

## 1. Problem

Chat-to-trade agents treat a language model as a broker. A pasted ticker becomes a market order. There is no frozen size, no ledger, no halt, and no defined-risk overlay. The failure mode is not a bad SMA. It is an unconstrained `buy`.

## 2. One sentence

**The model may research. Veto decides.**

## 3. Architecture

Closed daily bars → fresh SMA 10/30, ranked by strength → `check_entry` → stock: gap-capped buy + 1-lot collar; crypto: gap-capped buy + 8% poll stop → reconcile fills/fees → halt on unknown order, qty mismatch, or 5% drawdown. Baseline is the only arm that talks to Alpaca. MCP and Streamlit cannot bypass the desk.

## 4. Live veto / HOLD table

Do not invent a cross. If the tape is HOLD, show HOLD. Typical row: `NVDA  HOLD  none  no_fresh_cross`. A reject (when a cross exists) looks like `correlation_cap:2`, `max_positions`, or `run_halted`. `veto explain NVDA` and MCP `explain_decision` read that ledger reason.

## 5. Collar preview

`veto preview-collar AAPL` / MCP `preview_collar`. 1 long ~8% OTM put, 1 short ~8% OTM call, ~35 DTE, debit cap $1,500, one name. Prints an Alpaca CLI string. Does not submit. If overlay is live, `veto stops` skips the poll flatten.

## 6. MCP tools

Read: account, positions, halt status, decisions, explain, preview collar.  
Dry-run default: `scan_now`, `execute_pending`.  
Missing on purpose: `buy(symbol, qty)`. Halt reasons come from reconcile and drawdown, not a placeholder string.

## 7. Research honesty

Frozen SMA 10/30, $100k, 2022–2026 Alpaca replay: **+5.4%** account vs **+59%** 25/25/50 benchmark. Win rate 29%. 47% of exits were 8% stops. That is the prior lab, not this week’s score. A 5% invested book cannot look like NVDA buy-and-hold. See `docs/prior-research.md`.

## 8. Ask

Judges: a public repo, a $100k paper account, a defined-risk overlay, MCP that cannot order, a demo with **no buy button**, and a desk that halts. Paper trading is simulated. Repo: https://github.com/dancaldera/veto
