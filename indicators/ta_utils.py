import pandas as pd


def sma(series: pd.Series, length: int) -> pd.Series:
    """
    TradingView ta.sma equivalent.
    Causal rolling mean:
        sma[t] uses series[t-length+1 : t+1]
    """
    if length < 1:
        raise ValueError("length must be >= 1")

    return series.rolling(window=length, min_periods=length).mean()


def stdev(series: pd.Series, length: int) -> pd.Series:
    """
    TradingView ta.stdev equivalent.

    TradingView's ta.stdev uses population standard deviation,
    so ddof=0.
    """
    if length < 1:
        raise ValueError("length must be >= 1")

    return series.rolling(window=length, min_periods=length).std(ddof=0)


def rma(series: pd.Series, length: int) -> pd.Series:
    """
    TradingView ta.rma equivalent.

    RMA uses:
        first value = SMA of first length values
        next value  = (prev_rma * (length - 1) + current) / length

    This implementation is causal and avoids future leakage.
    """
    if length < 1:
        raise ValueError("length must be >= 1")

    values = pd.to_numeric(series, errors="coerce")
    out = pd.Series(index=values.index, dtype="float64")

    valid_count = 0
    seed_values = []
    prev = None

    for i, value in enumerate(values):
        if pd.isna(value):
            out.iloc[i] = pd.NA
            continue

        if prev is None:
            seed_values.append(value)
            valid_count += 1

            if valid_count < length:
                out.iloc[i] = pd.NA
            else:
                prev = sum(seed_values[-length:]) / length
                out.iloc[i] = prev
        else:
            prev = (prev * (length - 1) + value) / length
            out.iloc[i] = prev

    return out


def true_range(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    """
    TradingView True Range logic:

    TR[t] = max(
        high[t] - low[t],
        abs(high[t] - close[t-1]),
        abs(low[t] - close[t-1])
    )

    For the first row, where close[t-1] is unavailable:
        TR[t] = high[t] - low[t]
    """
    high = pd.to_numeric(high, errors="coerce")
    low = pd.to_numeric(low, errors="coerce")
    close = pd.to_numeric(close, errors="coerce")

    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    tr.loc[prev_close.isna()] = high - low

    return tr


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int,
) -> pd.Series:
    """
    TradingView ta.atr equivalent:
        ATR = ta.rma(true_range, length)
    """
    return rma(true_range(high, low, close), length)