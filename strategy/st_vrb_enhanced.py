import numpy as np
import pandas as pd

from .base import Strategy

DEFAULT_PARAMS = {
    "st_length": 20,
    "st_factor": 5.5,
    "vb_length": 24,
    "vb_mult": 2.5,
    "vb_atr_mult": 1,
    "use_short": True,
    "st_touch_pct": 0.01,
    "vrb_touch_pct": 0.05,
    "take_profit_pct": 0.1,
    "stop_loss_pct": 0.03,
}

# Pine's `math.max(VRB_upper - VRB_lower, syminfo.mintick)` equivalent.
_MIN_VRB_RANGE = 1e-7


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
    Ported from pine_files/strategy/st_vrb_enhanced.txt.

    The public parameter interface is intentionally the same as
    st_vrb_clean. The behavioral difference is the final execution
    resolver: each bar runs through one ordered branch only:

        B1, S1, B2, S2, B3, S3, long SL, short SL, long TP, short TP

    Directional B/S signals therefore take priority over risk exits, and
    a single bar can produce at most one action branch. B3/S3 are
    close-only signals. B1/B2/S1/S2 reset the stop/take-profit reference
    price to the signal bar's close, matching the enhanced Pine script's
    `positionReferencePrice := close`.
    """
    out = df.copy()

    use_short = params.get("use_short", False)
    st_touch_pct = params["st_touch_pct"]
    vrb_touch_pct = params["vrb_touch_pct"]
    take_profit_pct = params["take_profit_pct"]
    stop_loss_pct = params["stop_loss_pct"]

    st_dir = pd.to_numeric(out["st_direction"], errors="coerce").to_numpy(dtype=float)
    st_val = pd.to_numeric(out["st_value"], errors="coerce").to_numpy(dtype=float)
    vrb_upper = pd.to_numeric(out["reversal_upper"], errors="coerce").to_numpy(dtype=float)
    vrb_lower = pd.to_numeric(out["reversal_lower"], errors="coerce").to_numpy(dtype=float)
    close = pd.to_numeric(out["close"], errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(out["high"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(out["low"], errors="coerce").to_numpy(dtype=float)
    n = len(out)
    prev_st_dir = np.concatenate(([np.nan], st_dir[:-1]))

    bull_st = st_dir == -1
    bear_st = st_dir == 1

    main_buy = bull_st & (prev_st_dir == 1)
    main_sell = bear_st & (prev_st_dir == -1)

    with np.errstate(invalid="ignore", divide="ignore"):
        touch_blue = bull_st & (np.abs(low - st_val) / close <= st_touch_pct)
        touch_red = bear_st & (np.abs(high - st_val) / close <= st_touch_pct)

        vrb_range = np.maximum(vrb_upper - vrb_lower, _MIN_VRB_RANGE)
        vrb_ratio = (close - vrb_lower) / vrb_range
        touch_vrb_lower = vrb_ratio <= vrb_touch_pct
        touch_vrb_upper = vrb_ratio >= (1.0 - vrb_touch_pct)

    long_reason = np.where(main_buy, 1, np.where(touch_blue, 2, np.where(touch_vrb_lower, 3, 0)))
    short_reason = np.where(main_sell, 1, np.where(touch_red, 2, np.where(touch_vrb_upper, 3, 0)))

    long_signal = long_reason > 0
    short_signal = short_reason > 0
    only_long_signal = long_signal & ~short_signal
    only_short_signal = short_signal & ~long_signal

    events: list[list[str]] = [[] for _ in range(n)]

    position = None  # "long" | "short" | None
    reference_price = np.nan
    will_close = False
    open_side = None  # "long" | "short" | None

    for i in range(n):
        # Apply the order queued by row[i-1], filled at open[i].
        if will_close and position is not None:
            events[i].append(f"{position}_exit")
            position = None
        if open_side is not None:
            events[i].append(f"{open_side}_entry")
            position = open_side

        will_close = False
        open_side = None

        c = close[i]
        has_long = position == "long"
        has_short = position == "short"
        has_none = position is None
        has_reference = not np.isnan(reference_price)

        long_stop = has_long and has_reference and c <= reference_price * (1 - stop_loss_pct)
        short_stop = has_short and has_reference and c >= reference_price * (1 + stop_loss_pct)
        long_take_profit = has_long and has_reference and c >= reference_price * (1 + take_profit_pct)
        short_take_profit = has_short and has_reference and c <= reference_price * (1 - take_profit_pct)

        # Exactly one branch may queue an action for the next bar.
        if only_long_signal[i] and long_reason[i] == 1:
            if has_none or has_short:
                will_close = has_short
                open_side = "long"
            reference_price = c

        elif only_short_signal[i] and short_reason[i] == 1:
            if use_short:
                if has_none or has_long:
                    will_close = has_long
                    open_side = "short"
                reference_price = c
            elif has_long:
                will_close = True
                reference_price = np.nan

        elif only_long_signal[i] and long_reason[i] == 2:
            if has_none or has_short:
                will_close = has_short
                open_side = "long"
            reference_price = c

        elif only_short_signal[i] and short_reason[i] == 2:
            if use_short:
                if has_none or has_long:
                    will_close = has_long
                    open_side = "short"
                reference_price = c
            elif has_long:
                will_close = True
                reference_price = np.nan

        elif only_long_signal[i] and long_reason[i] == 3:
            if has_short:
                will_close = True
                reference_price = np.nan

        elif only_short_signal[i] and short_reason[i] == 3:
            if has_long:
                will_close = True
                reference_price = np.nan

        elif long_stop:
            will_close = True
            reference_price = np.nan

        elif short_stop:
            will_close = True
            reference_price = np.nan

        elif long_take_profit:
            will_close = True
            reference_price = np.nan

        elif short_take_profit:
            will_close = True
            reference_price = np.nan

    out["long_reason"] = long_reason
    out["short_reason"] = short_reason
    out["signal"] = [",".join(e) if e else np.nan for e in events]

    return out


STRATEGY = Strategy(
    name="st_vrb_enhanced",
    build_indicators=build_indicators,
    generate_signals=generate_signals,
    params=dict(DEFAULT_PARAMS),
)
