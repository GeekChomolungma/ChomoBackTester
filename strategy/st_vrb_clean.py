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

# Pine's `denom = math.max(reversalUpper - reversalLower, 0.0000001)` floor,
# substituted for syminfo.mintick (no tick-size metadata in this dataset).
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
    Ported from pine_files/strategy/st_vrb_clean.txt.

    Three-tier signal priority, computed causally from row[t]:
        1 (strong) - SuperTrend direction flip (mainBuy/mainSell)
        2 (strong) - price touches the SuperTrend line while direction
                     already favors that side (touchBlue/touchRed)
        3 (weak)   - price touches a volatility-band boundary
                     (touchVrbLower/touchVrbUpper); this tier only ever
                     *closes* an existing position, it never opens one
    `long_reason`/`short_reason` (0-3) record which tier fired, mirroring
    the B1/B2/B3 and S1/S2/S3 labels in the original Pine plotshapes.

    Not ported from the Pine source (out of scope for this backtester):
    alert-message payloads, the fromTime/toTime input-window filter (this
    repo scopes date ranges via file/row selection instead), and
    strategy.* position sizing (this repo only reasons about entry/exit
    price + side, not notional amount).

    ST_up/ST_dn (the Pine strategy's two separate line inputs) are not
    reproduced as separate columns: ST_up only carries a value while
    st_direction == 1 (bearish) and there it equals st_value; ST_dn only
    carries a value while st_direction == -1 (bullish) and there it also
    equals st_value. So `st_value` alone (gated by st_direction) is
    sufficient and this strategy reuses indicators.super_trend as-is.

    State (position/entry_price/mainEntryActive) evolves once per bar,
    same as `strategy.position_size`/`position_avg_price` in Pine under
    default (non-intrabar) order-fill timing: a decision made from row[t]
    queues an order that fills at open[t+1], and that fill is what the
    row[t+1] decision then sees as "current position". This matches the
    project's no-lookahead protocol (see indicators/__init__.py) and the
    t -> t+1 execution offset used by strategy/st_vol_band_reversal.py.
    Pyramiding is disabled (matches pine's `pyramiding=0`): an entry
    signal in the direction of an already-open position is a no-op; an
    entry signal opposite an open position closes it and opens the new
    side on the same fill bar (reported as e.g. "long_exit,short_entry").
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
    open_ = pd.to_numeric(out["open"], errors="coerce").to_numpy(dtype=float)

    n = len(out)
    prev_st_dir = np.concatenate(([np.nan], st_dir[:-1]))

    bull_st = st_dir == -1
    bear_st = st_dir == 1

    # ta.crossunder(ST_dir, 0) / ta.crossover(ST_dir, 0); ST_dir only ever
    # takes values -1/1, so a cross through 0 is just a flip of sign.
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

    strong_long = (long_reason == 1) | (long_reason == 2)
    strong_short = (short_reason == 1) | (short_reason == 2)
    long_signal = long_reason > 0
    short_signal = short_reason > 0

    events: list[list[str]] = [[] for _ in range(n)]

    position = None  # "long" | "short" | None
    entry_price = None
    main_entry_active = False
    will_close = False
    open_side = None  # "long" | "short" | None

    for i in range(n):
        # --- apply the fill queued by the previous bar's decision, using open[i] ---
        if will_close and position is not None:
            events[i].append(f"{position}_exit")
            position = None
            entry_price = None
        if open_side is not None:
            events[i].append(f"{open_side}_entry")
            position = open_side
            entry_price = open_[i]
        will_close = False
        open_side = None

        # --- decide this bar's actions from row[i], to be filled at open[i+1] ---
        c = close[i]

        long_sl = position == "long" and c <= entry_price * (1 - stop_loss_pct)
        short_sl = position == "short" and c >= entry_price * (1 + stop_loss_pct)

        if long_sl and not strong_long[i] and not strong_short[i]:
            will_close = True
            main_entry_active = False
        if short_sl and not strong_short[i] and not strong_long[i]:
            will_close = True
            main_entry_active = False

        long_tp = main_entry_active and position == "long" and c >= entry_price * (1 + take_profit_pct)
        short_tp = main_entry_active and position == "short" and c <= entry_price * (1 - take_profit_pct)

        if long_tp or short_tp:
            will_close = True
            main_entry_active = False

        # same-bar long/short conflicts are skipped entirely, same as Pine
        if long_signal[i] and not short_signal[i]:
            reason = long_reason[i]
            if reason in (1, 2):
                if position != "long":
                    will_close = True
                    open_side = "long"
                    main_entry_active = reason == 1
            elif reason == 3:
                will_close = True
                main_entry_active = False

        if short_signal[i] and not long_signal[i]:
            reason = short_reason[i]
            if reason in (1, 2):
                if use_short:
                    if position != "short":
                        will_close = True
                        open_side = "short"
                        main_entry_active = reason == 1
                else:
                    will_close = True
                    main_entry_active = False
            elif reason == 3:
                will_close = True
                main_entry_active = False

    out["long_reason"] = long_reason
    out["short_reason"] = short_reason
    out["signal"] = [",".join(e) if e else np.nan for e in events]

    return out


STRATEGY = Strategy(
    name="st_vrb_clean",
    build_indicators=build_indicators,
    generate_signals=generate_signals,
    params=dict(DEFAULT_PARAMS),
)
