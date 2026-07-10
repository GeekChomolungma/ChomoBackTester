import numpy as np
import pandas as pd

from .base import Strategy

DEFAULT_PARAMS = {
    "st_length": 14,
    "st_factor": 5.0,
    "vb_length": 20,
    "vb_mult": 2.0,
    "vb_atr_mult": 1.5,
    "use_band_filter": False,
}


def build_indicators(params: dict) -> list[dict]:
    return [
        {
            "name": "super_trend",
            "params": {
                "length": params["st_length"],
                "factor": params["st_factor"],
                "source": "close",
                "value_col": "st_value",
                "direction_col": "st_direction",
            },
        },
        {
            "name": "volatility_band",
            "params": {
                "length": params["vb_length"],
                "mult": params["vb_mult"],
                "atr_mult": params["vb_atr_mult"],
                "source": "close",
                "upper_col": "reversal_upper",
                "lower_col": "reversal_lower",
            },
        },
    ]


def generate_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """
    SuperTrend flip-and-reverse, optionally gated by the volatility band.

    Time protocol: the decision at bar t only reads data through row[t]
    (st_direction[t], close[t], reversal bands[t]). The resulting trade
    is executed on bar t+1 using open[t+1] as the fill price, so the
    `signal` column is written one row after the bar that produced the
    decision. This keeps the output causal by construction, consistent
    with the no-lookahead protocol documented in indicators/__init__.py,
    and means downstream consumers (backtest.trades) can read `signal`
    directly as "the bar the trade actually filled on" with no offset
    logic of their own.
    """
    out = df.copy()
    use_band_filter = params.get("use_band_filter", False)

    direction = out["st_direction"]
    prev_direction = direction.shift(1)

    # st_direction is a nullable Int64; comparisons against NA (warm-up
    # rows) yield pd.NA under Kleene logic, so fold to plain bool early.
    turned_bullish = ((direction == -1) & (prev_direction == 1)).fillna(False).astype(bool)
    turned_bearish = ((direction == 1) & (prev_direction == -1)).fillna(False).astype(bool)

    if use_band_filter:
        turned_bullish &= (out["close"] <= out["reversal_lower"]).fillna(False)
        turned_bearish &= (out["close"] >= out["reversal_upper"]).fillna(False)

    long_entry_at = turned_bullish.shift(1, fill_value=False).astype(bool)
    short_entry_at = turned_bearish.shift(1, fill_value=False).astype(bool)

    n = len(out)
    events: list[list[str]] = [[] for _ in range(n)]

    position = None  # "long" | "short" | None
    for i in range(n):
        if long_entry_at.iloc[i]:
            if position == "short":
                events[i].append("short_exit")
            events[i].append("long_entry")
            position = "long"
        elif short_entry_at.iloc[i]:
            if position == "long":
                events[i].append("long_exit")
            events[i].append("short_entry")
            position = "short"

    out["signal"] = [",".join(e) if e else np.nan for e in events]

    return out


STRATEGY = Strategy(
    name="st_vol_band_reversal",
    build_indicators=build_indicators,
    generate_signals=generate_signals,
    params=dict(DEFAULT_PARAMS),
)
