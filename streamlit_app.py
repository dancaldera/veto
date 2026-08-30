"""Streamlit Cloud entrypoint. Do not rely on `pip install -e .` (Cloud skips it)."""

from __future__ import annotations

from pathlib import Path
import sys

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from veto.demo import render

render()
