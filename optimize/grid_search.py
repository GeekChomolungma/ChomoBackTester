import itertools

import pandas as pd

from backtest import compute_metrics, extract_trades
from strategy import build_enriched
from strategy.base import Strategy


def run_grid_search(
    df: pd.DataFrame,
    strategy: Strategy,
    param_grid: dict[str, list],
    base_params: dict | None = None,
    rebuild_indicators: bool = True,
    report_start=None,
    datetime_col: str = "datetime",
) -> pd.DataFrame:
    """
    Sweep every combination in param_grid through generate_signals ->
    extract_trades -> compute_metrics, and collect one result row per
    combination: the swept param values plus every metric key.

    `rebuild_indicators` controls what `df` is expected to be, and is the
    one thing to get right before calling this:
      - True (default): `df` is the raw, not-yet-enriched OHLCV frame.
        build_indicators/build_features run again for every combo, so use
        this when any swept key feeds build_indicators (e.g. st_length).
      - False: `df` is already an enriched frame (see strategy.build_enriched
        / this module's own build_enriched import), built once by the
        caller and reused across every combo -- use this when every swept
        key only affects generate_signals (e.g. a touch-distance
        threshold), to avoid recomputing indicators once per combo for
        params that never touch them.

    `base_params` holds any non-swept param overrides held fixed for the
    whole sweep (indicator- or strategy-level either way).

    If `df` carries lookback rows before the intended backtest window (see
    optimize.date_window.slice_with_lookback), pass that window's real
    start as `report_start`: rows before it are dropped after
    generate_signals runs (which needs the lookback rows to see a real
    previous bar for any row[t-1]-comparing logic) but before
    extract_trades/compute_metrics, so the lookback rows never leak into
    the reported metrics.
    """
    keys = list(param_grid.keys())
    value_lists = [param_grid[k] for k in keys]
    fixed = base_params or {}

    rows = []
    for combo in itertools.product(*value_lists):
        overrides = dict(zip(keys, combo))
        params = {**strategy.params, **fixed, **overrides}

        enriched = build_enriched(df, strategy, {**fixed, **overrides}) if rebuild_indicators else df

        signaled = strategy.generate_signals(enriched, params)
        if report_start is not None:
            signaled = signaled[signaled[datetime_col] >= pd.Timestamp(report_start)]

        trades = extract_trades(signaled)
        metrics = compute_metrics(trades)

        rows.append({**overrides, **metrics})

    return pd.DataFrame(rows)
