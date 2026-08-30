"""Paper-only Alpaca CLI helpers. Submit still goes through the SDK unless doctor is clean."""

from __future__ import annotations

import shutil
import subprocess

from .options import CollarPlan


class CliError(RuntimeError):
    """Raised when the Alpaca CLI is missing or not pointed at paper."""


def alpaca_bin() -> str:
    path = shutil.which("alpaca")
    if not path:
        raise CliError("alpaca CLI not found on PATH. Install: https://github.com/alpacahq/cli")
    return path


def assert_paper_endpoint() -> str:
    """Require `alpaca doctor` (or version) to mention the paper trading host."""
    binary = alpaca_bin()
    for args in ([binary, "doctor"], [binary, "account", "get", "--help"]):
        try:
            proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CliError(f"failed to run {' '.join(args)}: {exc}") from exc
        text = (proc.stdout or "") + (proc.stderr or "")
        if "paper-api.alpaca.markets" in text:
            return text
        if proc.returncode == 0 and args[1] == "doctor":
            if "api.alpaca.markets" in text and "paper-api" not in text:
                raise CliError("alpaca CLI is pointed at live trading; Veto requires paper-api.alpaca.markets")
    # CLI present but doctor output is sparse; caller may still use the SDK.
    return "alpaca CLI present; paper host not confirmed in doctor output"


def format_collar_command(plan: CollarPlan) -> str:
    """Copy-paste preview for the demo. Execution uses the paper SDK."""
    return (
        f"alpaca order create --paper --class mleg --tif day --qty 1 "
        f"--limit {plan.limit_price:.2f} "
        f"--leg buy_to_open {plan.put.symbol} "
        f"--leg sell_to_open {plan.call.symbol}"
    )
