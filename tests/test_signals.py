from __future__ import annotations

import numpy as np
import pandas as pd

from veto.signals import cross_strength, sma_cross_signal


def test_short_history_is_hold():
    assert sma_cross_signal(np.linspace(100, 110, 5)) == "HOLD"


def test_fresh_up_cross_is_buy():
    close = np.r_[np.full(40, 100.0), 200.0]
    assert sma_cross_signal(close) == "BUY"


def test_fresh_down_cross_is_sell():
    close = np.r_[np.full(40, 200.0), 50.0]
    assert sma_cross_signal(close) == "SELL"


def test_no_cross_while_fast_stays_above_is_hold():
    close = np.r_[np.full(40, 100.0), 200.0, 201.0]
    assert sma_cross_signal(close) == "HOLD"


def test_stronger_jump_ranks_higher():
    weak = np.r_[np.full(40, 100.0), 120.0]
    strong = np.r_[np.full(40, 100.0), 200.0]
    assert cross_strength(strong) > cross_strength(weak)
    assert pd.notna(cross_strength(strong))
