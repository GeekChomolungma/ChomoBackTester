import itertools

import pandas as pd

from backtest import compute_metrics, extract_trades
from strategy.base import Strategy


def run_signal_grid_search(
    enriched: pd.DataFrame,
    strategy: Strategy,
    param_grid: dict[str, list],
    base_params: dict | None = None,
    report_start=None,
    datetime_col: str = "datetime",
) -> pd.DataFrame:
    """
    Like optimize.grid_search.run_grid_search, but for sweeps where every
    swept key only affects generate_signals (not build_indicators) -- e.g.
    st_vrb_clean's st_touch_pct/vrb_touch_pct. `enriched` is built once by
    the caller (strategy.build_enriched) and reused across every combo
    instead of being recomputed per combo, since the indicator columns
    don't change.

    If `enriched` carries extra lookback rows before the intended backtest
    window (see optimize.date_window.slice_with_lookback), pass that
    window's real start as `report_start`: after generate_signals runs
    (which needs the lookback rows to see a real previous bar), rows
    before `report_start` are dropped before extract_trades/compute_metrics
    so the lookback rows only serve to seed generate_signals's own
    row[t-1] comparisons and never leak into the reported metrics.
    """
    keys = list(param_grid.keys())
    value_lists = [param_grid[k] for k in keys]
    base = {**strategy.params, **(base_params or {})}

    rows = []
    for combo in itertools.product(*value_lists):
        overrides = dict(zip(keys, combo))
        params = {**base, **overrides}

        signaled = strategy.generate_signals(enriched, params)
        if report_start is not None:
            signaled = signaled[signaled[datetime_col] >= pd.Timestamp(report_start)]

        trades = extract_trades(signaled)
        metrics = compute_metrics(trades)

        rows.append({**overrides, **metrics})

    return pd.DataFrame(rows)
