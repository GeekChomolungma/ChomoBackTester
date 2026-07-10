import itertools

import pandas as pd

from backtest import compute_metrics, extract_trades
from strategy import build_enriched
from strategy.base import Strategy


def run_grid_search(
    df: pd.DataFrame,
    strategy: Strategy,
    param_grid: dict[str, list],
) -> pd.DataFrame:
    """
    Sweep every combination in param_grid (indicator params and/or
    strategy params -- both live in the same flat params dict, see
    strategy.base.Strategy) through build_enriched -> generate_signals
    -> extract_trades -> compute_metrics, and collect one result row
    per combination: the swept param values plus every metric key.
    """
    keys = list(param_grid.keys())
    value_lists = [param_grid[k] for k in keys]

    rows = []
    for combo in itertools.product(*value_lists):
        overrides = dict(zip(keys, combo))
        params = {**strategy.params, **overrides}

        enriched = build_enriched(df, strategy, overrides)
        signaled = strategy.generate_signals(enriched, params)
        trades = extract_trades(signaled)
        metrics = compute_metrics(trades)

        rows.append({**overrides, **metrics})

    return pd.DataFrame(rows)
