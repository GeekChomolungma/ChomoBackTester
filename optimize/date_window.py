import pandas as pd


def slice_with_lookback(
    df: pd.DataFrame,
    start=None,
    end=None,
    lookback_bars: int = 0,
    datetime_col: str = "datetime",
) -> pd.DataFrame:
    """
    Row-slice an already-enriched dataframe to [start, end] (inclusive),
    plus `lookback_bars` extra rows immediately before `start`.

    Apply this AFTER strategy.build_enriched (indicators need real
    history for warmup -- see indicators/__init__.py's no-lookahead
    protocol) and BEFORE strategy.generate_signals, so indicator warmup
    reflects full history while the reported window is still exactly
    [start, end].

    `lookback_bars=1` is the usual choice for strategies whose
    generate_signals compares row[t] against row[t-1] (e.g. a direction
    flip/crossover): without it, the very first in-window row has no
    prior row to compare against and can silently miss a flip that
    actually happened right at the window boundary. Trades filled from
    a decision made on the lookback row itself are legitimate (that
    decision fills at the next bar's open, which is already inside the
    window) -- only the lookback row's own signal (always empty, since
    it is the first row generate_signals sees) needs to be dropped
    before computing trades/metrics, which callers do by re-filtering
    on `datetime_col >= start` after generate_signals runs.
    """
    df = df.reset_index(drop=True)

    in_range = pd.Series(True, index=df.index)
    if start is not None:
        in_range &= df[datetime_col] >= pd.Timestamp(start)
    if end is not None:
        in_range &= df[datetime_col] <= pd.Timestamp(end)

    matched = df.index[in_range]
    if len(matched) == 0:
        return df.iloc[0:0]

    start_pos = max(matched[0] - lookback_bars, 0)
    end_pos = matched[-1]

    return df.iloc[start_pos : end_pos + 1].reset_index(drop=True)
