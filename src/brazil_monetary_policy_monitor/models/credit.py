"""Pure credit-transmission calculations."""

from __future__ import annotations

import math


def real_balance_growth_percent(
    current_balance: float,
    year_ago_balance: float,
    inflation_12m_percent: float,
) -> float:
    """Return 12-month real growth of a nominal balance.

    ``inflation_12m_percent`` is the price-level change over exactly the same
    twelve-month interval as the nominal balance comparison.
    """

    values = (current_balance, year_ago_balance, inflation_12m_percent)
    if any(not math.isfinite(value) for value in values):
        raise ValueError("credit-growth inputs must be finite")
    if current_balance < 0:
        raise ValueError("current_balance cannot be negative")
    if year_ago_balance <= 0:
        raise ValueError("year_ago_balance must be positive")
    inflation_factor = 1.0 + inflation_12m_percent / 100.0
    if inflation_factor <= 0:
        raise ValueError("inflation factor must be positive")
    return ((current_balance / year_ago_balance) / inflation_factor - 1.0) * 100.0
