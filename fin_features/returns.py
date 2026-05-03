import numpy as np
import pandas as pd


def add_log_return(
    df: pd.DataFrame,
    source: str = "close",
    output_col: str = "target_logreturn",
) -> pd.DataFrame:
    out = df.copy()

    close = out[source].astype(float)
    out[output_col] = np.log(close / close.shift(1))

    return out