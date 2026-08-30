"""Render docs/one-pager.pdf and docs/slides.pdf. Run: python docs/render_pdfs.py"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
INK = HexColor("#111111")
MUTED = HexColor("#444444")
RULE = HexColor("#C43A3A")
PAPER = HexColor("#F7F5F0")
SLIDE_BG = HexColor("#101418")
SLIDE_INK = HexColor("#F4F1EA")
SLIDE_MUTED = HexColor("#A8B0B8")
SLIDE_RULE = HexColor("#E24B4B")


def _wrap(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if c.stringWidth(trial, font, size) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def one_pager(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=LETTER)
    c.setTitle("Veto — one page")
    c.setAuthor("Veto")
    c.setSubject("Alpaca AI Trading Agents Hackathon eligibility write-up")
    width, height = LETTER
    c.setFillColor(PAPER)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    left = 0.6 * inch
    top = height - 0.5 * inch
    max_w = width - 1.2 * inch

    c.setFillColor(RULE)
    c.rect(left, top - 2, 1.4 * inch, 4, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Times-Bold", 28)
    c.drawString(left, top - 32, "Veto")
    c.setFont("Times-Italic", 11)
    c.setFillColor(MUTED)
    c.drawString(left, top - 50, "The model may research. Veto decides.")
    c.setFont("Helvetica", 8)
    c.drawRightString(width - left, top - 32, "Alpaca AI Trading Agents Hackathon")
    c.drawRightString(width - left, top - 44, "github.com/dancaldera/veto")
    c.drawRightString(width - left, top - 56, "bszv8nabdvvipmbetdvtgv.streamlit.app")

    y = top - 80
    body = (
        "Veto is a fail-closed Alpaca paper desk. An LLM can inspect, explain, and preview. "
        "It cannot size or send an order. Frozen rules authorize every fill. Stock entries "
        "carry a defined-risk options overlay. Crypto keeps an 8% fill-derived poll stop. "
        "Shadows never touch the broker."
    )
    c.setFillColor(INK)
    c.setFont("Times-Roman", 10)
    for line in _wrap(c, body, "Times-Roman", 10, max_w):
        c.drawString(left, y, line)
        y -= 13

    def heading(label: str) -> None:
        nonlocal y
        y -= 8
        c.setFillColor(RULE)
        c.rect(left, y + 2, 10, 10, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left + 16, y + 3, label)
        y -= 14

    def para(text: str, size: float = 9) -> None:
        nonlocal y
        c.setFillColor(INK)
        c.setFont("Times-Roman", size)
        for line in _wrap(c, text, "Times-Roman", size, max_w):
            c.drawString(left, y, line)
            y -= 11.5

    heading("AI logic")
    para(
        "The language model is not the authorization layer. Closed daily bars produce a fresh "
        "SMA 10/30 signal. Same-day buys are ranked by cross strength, not alphabet. check_entry "
        "is the only path to a buy intent. MCP tools are read, explain, collar preview, and dry-run "
        "scan/execute. There is no buy(symbol, qty). Regime and FinBERT news arms are declared "
        "shadows (shadow_regime, shadow_regime_news). They are not live this week; a fake news "
        "model would be a lie. When they run, they still cannot call buy_limit or submit_collar."
    )

    heading("Risk gates (frozen)")
    gates = [
        "Account — $100,000 start, no margin, paper endpoint hardcoded (PK keys only; AK rejected).",
        "Clip — $625; max 8 names / $5,000; crypto 4 / $2,500; stock 6 / $3,750.",
        "Correlation — reject at ≥0.80 with more than one holding (60 daily returns).",
        "Gap — skip if live price is >2% (stock) or >3% (crypto) past the signal close.",
        "Stop — 8% from ledger average entry, polled. Not a resting broker stop. Skip flatten if a collar put is live.",
        "Overlay — 1-lot put/call, ~8% OTM, ~35 DTE, max debit $1,500, max 1 name. Else options_skipped, poll stop stays.",
        "Halt — unknown broker order, qty mismatch vs the fill ledger, or 5% high-water drawdown. New buys stop. Exits stay on.",
    ]
    c.setFont("Times-Roman", 9)
    for gate in gates:
        for i, line in enumerate(_wrap(c, gate, "Times-Roman", 9, max_w - 12)):
            c.drawString(left + (0 if i else 8), y, ("• " if i == 0 else "  ") + line if i == 0 else line)
            y -= 11
        y -= 1

    heading("Alpaca surface")
    para(
        "Trading API: gap-capped limit buys, MLEG collar, closes; paper=True is not configurable. "
        "MCP: get_account, get_positions, get_halt_status (real halt reasons), latest_decisions, "
        "explain_decision, preview_collar; scan_now and execute_pending default dry_run=true. "
        "CLI: veto scan, execute, preview-collar (prints the Alpaca CLI string), reconcile, stops."
    )

    heading("Paper-only")
    para(
        "Competition account is $100k, empty at init. Paper P&L is simulated. It is not live "
        "performance and not a forecast."
    )

    heading("Prior research (not this week’s P&L)")
    para(
        "A 2022-01-01 → 2026-08-29 replay of this frozen SMA book returned +5.4% at the $100k "
        "account vs +59% for a 25% stocks / 25% crypto / 50% cash benchmark. Win rate 29%. "
        "47% of exits were 8% poll stops. See docs/prior-research.md. Veto does not pitch that "
        "tape as an edge. It pitches a desk that knows how to refuse."
    )

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawString(left, 0.4 * inch, "One page for Alpaca eligibility. MIT. Paper trading only.")
    c.save()


def slides(path: Path) -> None:
    page = landscape((13.333 * inch, 7.5 * inch))  # 16:9 at 7.5" tall
    c = canvas.Canvas(str(path), pagesize=page)
    c.setTitle("Veto — 8 slides")
    c.setAuthor("Veto")
    c.setSubject("Alpaca AI Trading Agents Hackathon pitch")
    w, h = page

    decks = [
        (
            "01  /  Problem",
            "Chat-to-trade is not a risk desk.",
            [
                "A language model that can call buy(symbol, qty) is a broker with no size, no ledger, and no halt.",
                "The failure mode is not a bad SMA. It is an unconstrained order.",
                "Veto exists so the model can research without being allowed to fill.",
            ],
        ),
        (
            "02  /  One sentence",
            "The model may research. Veto decides.",
            [
                "Frozen rules size every order. The LLM inspects, explains, and previews.",
                "It cannot authorize a fill. Paper endpoint only.",
            ],
        ),
        (
            "03  /  Architecture",
            "Desk in the middle. Broker at the edge.",
            [
                "Closed daily bars → fresh SMA 10/30, ranked by cross strength → check_entry.",
                "Stock: gap-capped buy + 1-lot collar. Crypto: gap-capped buy + 8% poll stop.",
                "Reconcile fills/fees. Halt on unknown order, qty mismatch, or 5% drawdown.",
                "Baseline is the only arm that talks to Alpaca. Shadows cannot order.",
            ],
        ),
        (
            "04  /  Live tape",
            "Do not fake a cross. HOLD is allowed.",
            [
                "Today’s scan is HOLD. Typical row: NVDA  HOLD  none  no_fresh_cross.",
                "A reject, when a cross exists, looks like correlation_cap:2 or run_halted.",
                "veto explain NVDA and MCP explain_decision read that ledger reason.",
            ],
        ),
        (
            "05  /  Collar",
            "Defined-risk overlay. Preview is not a fill.",
            [
                "1 long ~8% OTM put + 1 short ~8% OTM call, ~35 DTE, max debit $1,500, one name.",
                "veto preview-collar AAPL prints the Alpaca CLI string. SDK places overlays.",
                "If a collar put is live, veto stops skips the poll flatten. Else crypto (and skipped collars) poll 8%.",
            ],
        ),
        (
            "06  /  MCP",
            "No unconstrained buy tool.",
            [
                "Read: get_account, get_positions, get_halt_status, latest_decisions, explain_decision, preview_collar.",
                "Dry-run default: scan_now, execute_pending. Live still goes through check_entry.",
                "Halt reasons are real: reconciliation_failed or drawdown_halt — not a placeholder.",
            ],
        ),
        (
            "07  /  Honesty",
            "+5.4% vs +59%. That is the prior lab.",
            [
                "Frozen SMA 10/30, $100k, 2022–2026 Alpaca replay: +5.4% account vs +59% 25/25/50 benchmark.",
                "Win rate 29%. 47% of exits were 8% poll stops. A 5% invested book cannot look like NVDA.",
                "Veto does not pitch that tape as an edge. See docs/prior-research.md.",
            ],
        ),
        (
            "08  /  Ask",
            "A desk that knows how to refuse.",
            [
                "Public repo, $100k paper, options overlay, MCP that cannot order, demo with no buy button.",
                "Reconcile can halt. Stops poll. Drawdown 5% stops new buys. Exits stay on.",
                "Demo: bszv8nabdvvipmbetdvtgv.streamlit.app  ·  github.com/dancaldera/veto",
            ],
        ),
    ]

    for i, (kicker, title, bullets) in enumerate(decks, start=1):
        c.setFillColor(SLIDE_BG)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColor(SLIDE_RULE)
        c.rect(0, 0, 8, h, fill=1, stroke=0)
        c.setFillColor(SLIDE_MUTED)
        c.setFont("Helvetica", 11)
        c.drawString(0.7 * inch, h - 0.55 * inch, kicker)
        c.drawRightString(w - 0.6 * inch, h - 0.55 * inch, f"{i} / 8")
        c.setFillColor(SLIDE_INK)
        c.setFont("Times-Bold", 32)
        y = h - 1.35 * inch
        for line in _wrap(c, title, "Times-Bold", 32, w - 1.4 * inch):
            c.drawString(0.7 * inch, y, line)
            y -= 38
        y -= 10
        c.setStrokeColor(SLIDE_RULE)
        c.setLineWidth(2)
        c.line(0.7 * inch, y + 18, 2.2 * inch, y + 18)
        c.setFillColor(SLIDE_INK)
        c.setFont("Times-Roman", 16)
        for bullet in bullets:
            for j, line in enumerate(_wrap(c, bullet, "Times-Roman", 16, w - 1.6 * inch)):
                prefix = "·  " if j == 0 else "   "
                c.drawString(0.7 * inch, y, prefix + line)
                y -= 24
            y -= 8
        c.setFillColor(SLIDE_MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(0.7 * inch, 0.4 * inch, "Veto  ·  paper only  ·  the model may research")
        c.showPage()
    c.save()


def main() -> None:
    one_pager(ROOT / "one-pager.pdf")
    slides(ROOT / "slides.pdf")
    print(f"wrote {ROOT / 'one-pager.pdf'}")
    print(f"wrote {ROOT / 'slides.pdf'}")


if __name__ == "__main__":
    main()
