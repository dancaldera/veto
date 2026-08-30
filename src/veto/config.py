"""Frozen, hashed manifest for the Veto paper run."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import yaml


class RunConfigError(ValueError):
    """Raised when the Veto manifest is unsafe or drifted from the freeze."""


_CRYPTO = (
    "BTC/USD",
    "ETH/USD",
    "SOL/USD",
    "LTC/USD",
    "LINK/USD",
    "DOGE/USD",
    "AVAX/USD",
    "AAVE/USD",
)
_STOCKS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "NFLX")


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    fast_window: int
    slow_window: int
    timeframe: str
    stop_loss_pct: float
    require_fresh_cross_after_stop: bool


@dataclass(frozen=True)
class PortfolioConfig:
    position_notional: float
    max_positions: int
    max_gross_exposure: float
    max_crypto_positions: int
    max_crypto_exposure: float
    max_stock_positions: int
    max_stock_exposure: float
    correlation_window: int
    correlation_threshold: float
    correlation_matches_allowed: int
    drawdown_halt_pct: float


@dataclass(frozen=True)
class ExecutionConfig:
    stock_gap_limit_pct: float
    crypto_gap_limit_pct: float
    paper_only: bool
    use_margin: bool
    equity_slippage_bps: float
    crypto_taker_fee_bps: float


@dataclass(frozen=True)
class OptionsConfig:
    enabled: bool
    collar: bool
    put_otm_pct: float
    call_otm_pct: float
    target_dte: int
    max_premium: float
    max_names: int


@dataclass(frozen=True)
class ResearchConfig:
    regime_min_score: int
    feature_max_age_hours: int
    news_lookback_days: int
    news_min_observations: int
    negative_news_z: float
    arms: tuple[str, ...]


@dataclass(frozen=True)
class RunConfig:
    run_id: str
    starting_equity: float
    strategy: StrategyConfig
    portfolio: PortfolioConfig
    execution: ExecutionConfig
    options: OptionsConfig
    research: ResearchConfig
    crypto_symbols: tuple[str, ...]
    stock_symbols: tuple[str, ...]
    raw: dict[str, Any]
    fingerprint: str

    @property
    def symbols(self) -> tuple[tuple[str, str], ...]:
        return tuple((s, "crypto") for s in self.crypto_symbols) + tuple(
            (s, "stock") for s in self.stock_symbols
        )

    def gap_limit_pct(self, asset: str) -> float:
        return (
            self.execution.crypto_gap_limit_pct
            if asset == "crypto"
            else self.execution.stock_gap_limit_pct
        )


def _canonical(raw: dict[str, Any]) -> str:
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require(raw: dict[str, Any], key: str, parent: str = "config") -> Any:
    if key not in raw:
        raise RunConfigError(f"Missing {parent}.{key}")
    return raw[key]


def load_run_config(path: str | Path) -> RunConfig:
    path = Path(path)
    with path.open() as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise RunConfigError("Run config must be a YAML mapping")

    strategy_raw = _require(raw, "strategy")
    portfolio_raw = _require(raw, "portfolio")
    execution_raw = _require(raw, "execution")
    options_raw = _require(raw, "options")
    research_raw = _require(raw, "research")
    crypto_raw = _require(raw, "crypto")
    stocks_raw = _require(raw, "stocks")

    cfg = RunConfig(
        run_id=str(_require(raw, "run_id")),
        starting_equity=float(_require(raw, "starting_equity")),
        strategy=StrategyConfig(**strategy_raw),
        portfolio=PortfolioConfig(**portfolio_raw),
        execution=ExecutionConfig(**execution_raw),
        options=OptionsConfig(**options_raw),
        research=ResearchConfig(
            **{
                **research_raw,
                "arms": tuple(research_raw.get("arms", ())),
            }
        ),
        crypto_symbols=tuple(crypto_raw.get("symbols", ())),
        stock_symbols=tuple(stocks_raw.get("symbols", ())),
        raw=raw,
        fingerprint=sha256(_canonical(raw).encode()).hexdigest(),
    )
    _validate(cfg)
    return cfg


def _validate(cfg: RunConfig) -> None:
    if cfg.run_id != "veto":
        raise RunConfigError("run_id must be 'veto'")
    if cfg.starting_equity != 100_000:
        raise RunConfigError("starting_equity is frozen at 100000")
    if cfg.strategy.name != "sma_cross":
        raise RunConfigError("Veto baseline must remain sma_cross")
    if cfg.strategy.fast_window != 10 or cfg.strategy.slow_window != 30:
        raise RunConfigError("SMA windows are frozen at 10/30")
    if cfg.strategy.timeframe != "1d":
        raise RunConfigError("Veto is frozen to closed daily bars")
    if not cfg.strategy.require_fresh_cross_after_stop:
        raise RunConfigError("Veto requires a fresh SMA cross after a stopped position")
    if not cfg.execution.paper_only or cfg.execution.use_margin:
        raise RunConfigError("Veto must be paper-only with margin disabled")
    if not cfg.options.enabled or not cfg.options.collar:
        raise RunConfigError("Veto requires an enabled options collar overlay")
    if cfg.options.put_otm_pct != 8 or cfg.options.call_otm_pct != 8:
        raise RunConfigError("Collar offsets are frozen at 8%")
    if cfg.options.target_dte != 35 or cfg.options.max_premium != 1500 or cfg.options.max_names != 1:
        raise RunConfigError("Options overlay sizing is frozen")
    frozen = {
        "position_notional": (cfg.portfolio.position_notional, 625),
        "max_positions": (cfg.portfolio.max_positions, 8),
        "max_gross_exposure": (cfg.portfolio.max_gross_exposure, 5_000),
        "max_crypto_positions": (cfg.portfolio.max_crypto_positions, 4),
        "max_crypto_exposure": (cfg.portfolio.max_crypto_exposure, 2_500),
        "max_stock_positions": (cfg.portfolio.max_stock_positions, 6),
        "max_stock_exposure": (cfg.portfolio.max_stock_exposure, 3_750),
        "correlation_window": (cfg.portfolio.correlation_window, 60),
        "correlation_threshold": (cfg.portfolio.correlation_threshold, 0.80),
        "correlation_matches_allowed": (cfg.portfolio.correlation_matches_allowed, 1),
        "drawdown_halt_pct": (cfg.portfolio.drawdown_halt_pct, 5),
        "stock_gap_limit_pct": (cfg.execution.stock_gap_limit_pct, 2),
        "crypto_gap_limit_pct": (cfg.execution.crypto_gap_limit_pct, 3),
        "stop_loss_pct": (cfg.strategy.stop_loss_pct, 8),
    }
    changed = [name for name, (actual, expected) in frozen.items() if actual != expected]
    if changed:
        raise RunConfigError(f"Veto frozen values changed: {', '.join(changed)}")
    if cfg.crypto_symbols != _CRYPTO or cfg.stock_symbols != _STOCKS:
        raise RunConfigError("Watchlists do not match the archived 17-symbol set")
    if set(cfg.research.arms) != {"baseline", "shadow_regime", "shadow_regime_news"}:
        raise RunConfigError("research.arms must be baseline plus the two shadows")
    if cfg.portfolio.position_notional * cfg.portfolio.max_positions > cfg.portfolio.max_gross_exposure:
        raise RunConfigError("position_notional * max_positions exceeds max_gross_exposure")
