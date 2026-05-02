import pandas as pd

from .ta_utils import rma


def add_rsi(
    df: pd.DataFrame,
    length: int = 14,
    source: str = "close",
    output_col: str | None = None,
) -> pd.DataFrame:
    if source not in df.columns:
        raise ValueError(f"source column not found: {source}")

    output_col = output_col or f"rsi_{length}"

    out = df.copy()

    change = out[source].diff()  # source[t] - source[t-1]
    gain = change.clip(lower=0)
    loss = -change.clip(upper=0)

    avg_gain = rma(gain, length)
    avg_loss = rma(loss, length)

    rs = avg_gain / avg_loss

    out[output_col] = 100 - (100 / (1 + rs))

    out.loc[avg_loss == 0, output_col] = 100
    out.loc[avg_gain == 0, output_col] = 0
    out.loc[(avg_gain == 0) & (avg_loss == 0), output_col] = 50

    return out