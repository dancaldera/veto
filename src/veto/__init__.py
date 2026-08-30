"""Veto: a fail-closed Alpaca paper trading agent."""

from .config import RunConfig, RunConfigError, load_run_config
from .signals import cross_strength, sma_cross_signal

__all__ = [
    "RunConfig",
    "RunConfigError",
    "load_run_config",
    "cross_strength",
    "sma_cross_signal",
]
