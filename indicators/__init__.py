"""
=====================================================================
Time Alignment & No-Lookahead Protocol

This project enforces a strictly causal, no-lookahead computation rule
for all indicator calculations.

---------------------------------------------------------------------
1. Index Definition (Single Source of Truth)

Let `t` denote the Python integer index of a DataFrame row.

- A row is explicitly referred to as: row[t]
- The dataset is strictly ordered by time in ascending order
- Therefore:
    
    row[0] = earliest observation
    row[t] = the (t+1)-th observation in chronological order

IMPORTANT:

`t` is an INDEX, not a timestamp.

Time ordering is represented implicitly by index ordering.

---------------------------------------------------------------------
2. Historical and Future Data (Index-based Definition)

For any index t:

    Historical data up to and including t:
        rows[0:t+1]  → row[0] ... row[t]

    Strict future data:
        rows[t+1:]   → row[t+1], row[t+2], ...

Python slicing reminder:

    rows[0:t]   → row[0] ... row[t-1]
    rows[0:t+1] → row[0] ... row[t]

---------------------------------------------------------------------
3. Indicator Computation Rule (Causality Constraint)

For any indicator value computed at index t:

    indicator[t] MUST ONLY depend on:

        row[0], row[1], ..., row[t]

Formally:

    indicator[t] = f(rows[:t+1])

The following are strictly forbidden:

    - Accessing any row[k] where k > t
    - Using rows[t+1:] explicitly or implicitly
    - Using centered rolling windows
    - Any operation that leaks future information

---------------------------------------------------------------------
4. Kline Time Semantics (Interpretation Layer)

Although rows are indexed by `t`, each row[t] represents
a fully completed K-line.

This means:

    All values in row[t] (open, high, low, close, volume, etc.)
    are only known AFTER that K-line is completed.

Therefore:

    indicator[t] is computed AFTER row[t] is fully observed.

NOTE:

The DataFrame may contain time labels such as:
    - starttime
    - endtime
    - eventtime

These are metadata fields and DO NOT affect the causality rule,
which is defined strictly by index ordering.

---------------------------------------------------------------------
5. Decision Timing Constraint (for downstream usage)

Any decision based on row[t] (including indicator[t]):

    MUST NOT be applied to row[t]

    It can ONLY be applied at or after the beginning of row[t+1]

This ensures no look-ahead bias in trading logic.

---------------------------------------------------------------------
6. Design Principle

All indicators in this project must be:

    - Index-causal (strictly based on rows[:t+1])
    - Forward-safe
    - Free of look-ahead bias

Any violation of this protocol invalidates backtest correctness.

=====================================================================
"""

from .rsi import add_rsi
from .super_trend import add_super_trend
from .volatility_band import add_volatility_band

INDICATOR_REGISTRY = {
    "rsi": add_rsi,
    "super_trend": add_super_trend,
    "volatility_band": add_volatility_band,
}
def apply_indicator(df, name: str, **params):
    if name not in INDICATOR_REGISTRY:
        raise ValueError(f"Unknown indicator: {name}")

    return INDICATOR_REGISTRY[name](df, **params)