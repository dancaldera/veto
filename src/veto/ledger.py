"""SQLite event ledger. Positions are rebuilt from fills, never from broker cost basis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from .config import RunConfig


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _d(value: Any) -> Decimal:
    return Decimal(str(value or 0))


@dataclass(frozen=True)
class Position:
    portfolio: str
    symbol: str
    asset: str
    qty: Decimal
    avg_entry: Decimal
    cost_basis: Decimal


class LedgerError(RuntimeError):
    """Raised when ledger invariants or the frozen manifest are violated."""


_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL,
    config_json TEXT NOT NULL,
    starting_equity TEXT NOT NULL,
    broker_account_id TEXT,
    started_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    halted_at TEXT,
    halt_reason TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    portfolio TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset TEXT NOT NULL,
    strategy TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    bar_end TEXT NOT NULL,
    signal TEXT NOT NULL,
    signal_price TEXT NOT NULL,
    notional TEXT NOT NULL,
    strength REAL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'recorded',
    config_hash TEXT NOT NULL,
    UNIQUE(run_id, portfolio, symbol, bar_end, signal)
);

CREATE TABLE IF NOT EXISTS fills (
    fill_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    decision_id TEXT,
    portfolio TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset TEXT NOT NULL,
    side TEXT NOT NULL,
    qty TEXT NOT NULL,
    price TEXT NOT NULL,
    transaction_time TEXT NOT NULL,
    simulated INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    portfolio TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    equity TEXT NOT NULL,
    cash TEXT NOT NULL,
    drawdown_pct REAL NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(run_id, portfolio, captured_at, source)
);
"""


class RunLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def initialize_run(self, cfg: RunConfig, broker_account_id: str | None = None) -> None:
        row = self.conn.execute("SELECT * FROM runs WHERE run_id = ?", (cfg.run_id,)).fetchone()
        if row:
            if row["config_hash"] != cfg.fingerprint:
                raise LedgerError("Run manifest changed after initialization")
            return
        import json

        self.conn.execute(
            """INSERT INTO runs
               (run_id, config_hash, config_json, starting_equity, broker_account_id, started_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                cfg.run_id,
                cfg.fingerprint,
                json.dumps(cfg.raw, sort_keys=True),
                str(cfg.starting_equity),
                broker_account_id,
                utc_now(),
            ),
        )
        self.conn.commit()

    def assert_manifest(self, cfg: RunConfig) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM runs WHERE run_id = ?", (cfg.run_id,)).fetchone()
        if not row:
            raise LedgerError(f"Run {cfg.run_id!r} is not initialized")
        if row["config_hash"] != cfg.fingerprint:
            raise LedgerError("Run manifest hash does not match the frozen manifest")
        return row

    def run(self, run_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()

    def halt(self, run_id: str, reason: str) -> None:
        self.conn.execute(
            "UPDATE runs SET status = 'halted', halted_at = ?, halt_reason = ? WHERE run_id = ?",
            (utc_now(), reason, run_id),
        )
        self.conn.commit()

    def is_halted(self, run_id: str) -> bool:
        row = self.run(run_id)
        return bool(row and row["status"] != "active")

    def record_decision(self, row: dict[str, Any]) -> str:
        decision_id = row.get("decision_id") or str(uuid4())
        values = {
            "decision_id": decision_id,
            "decided_at": utc_now(),
            "strength": None,
            "action": "none",
            "reason": "",
            "status": "recorded",
            **row,
        }
        self.conn.execute(
            """INSERT OR IGNORE INTO decisions
               (decision_id, run_id, portfolio, symbol, asset, strategy, decided_at,
                bar_end, signal, signal_price, notional, strength, action, reason,
                status, config_hash)
               VALUES (:decision_id, :run_id, :portfolio, :symbol, :asset, :strategy,
                       :decided_at, :bar_end, :signal, :signal_price, :notional,
                       :strength, :action, :reason, :status, :config_hash)""",
            values,
        )
        existing = self.conn.execute(
            """SELECT decision_id FROM decisions
               WHERE run_id=? AND portfolio=? AND symbol=? AND bar_end=? AND signal=?""",
            (
                values["run_id"],
                values["portfolio"],
                values["symbol"],
                values["bar_end"],
                values["signal"],
            ),
        ).fetchone()
        self.conn.commit()
        return str(existing["decision_id"] if existing else decision_id)

    def decisions(
        self, run_id: str, portfolio: str | None = None, status: str | None = None
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM decisions WHERE run_id = ?"
        args: list[Any] = [run_id]
        if portfolio:
            sql += " AND portfolio = ?"
            args.append(portfolio)
        if status:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY bar_end, decided_at, symbol"
        return list(self.conn.execute(sql, args))

    def set_decision_status(self, decision_id: str, status: str, reason: str | None = None) -> None:
        if reason is None:
            self.conn.execute(
                "UPDATE decisions SET status=? WHERE decision_id=?", (status, decision_id)
            )
        else:
            self.conn.execute(
                "UPDATE decisions SET status=?, reason=? WHERE decision_id=?",
                (status, reason, decision_id),
            )
        self.conn.commit()

    def record_fill(self, row: dict[str, Any]) -> bool:
        values = {"decision_id": None, "simulated": 0, **row}
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO fills
               (fill_id, run_id, decision_id, portfolio, symbol, asset, side,
                qty, price, transaction_time, simulated)
               VALUES (:fill_id, :run_id, :decision_id, :portfolio, :symbol, :asset,
                       :side, :qty, :price, :transaction_time, :simulated)""",
            values,
        )
        self.conn.commit()
        return cur.rowcount == 1

    def fills(self, run_id: str, portfolio: str = "baseline") -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """SELECT * FROM fills WHERE run_id=? AND portfolio=?
                   ORDER BY transaction_time, fill_id""",
                (run_id, portfolio),
            )
        )

    def positions(self, run_id: str, portfolio: str = "baseline") -> dict[str, Position]:
        state: dict[str, dict[str, Any]] = {}
        for fill in self.fills(run_id, portfolio):
            symbol = fill["symbol"]
            item = state.setdefault(
                symbol,
                {"asset": fill["asset"], "qty": Decimal(0), "cost": Decimal(0)},
            )
            qty, price = _d(fill["qty"]), _d(fill["price"])
            if fill["side"] == "buy":
                item["cost"] += qty * price
                item["qty"] += qty
            else:
                sold = min(qty, item["qty"])
                avg = item["cost"] / item["qty"] if item["qty"] else Decimal(0)
                item["qty"] -= sold
                item["cost"] -= sold * avg
                if abs(item["qty"]) < Decimal("0.000000000001"):
                    item["qty"] = Decimal(0)
                    item["cost"] = Decimal(0)
        out: dict[str, Position] = {}
        for symbol, item in state.items():
            if item["qty"] <= 0:
                continue
            out[symbol] = Position(
                portfolio=portfolio,
                symbol=symbol,
                asset=item["asset"],
                qty=item["qty"],
                avg_entry=item["cost"] / item["qty"],
                cost_basis=item["cost"],
            )
        return out

    def option_overlay_names(self, run_id: str, portfolio: str = "baseline") -> set[str]:
        """Underlyings with a still-open option overlay (net long option qty > 0)."""
        return {
            symbol
            for symbol, pos in self.positions(run_id, portfolio).items()
            if pos.asset == "option"
        }
