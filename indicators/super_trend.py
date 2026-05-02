import numpy as np
import pandas as pd

from .ta_utils import rma


def _nz(series: pd.Series, value: float = 0.0) -> pd.Series:
    """
    Pine nz(x) equivalent for Series.
    Default replacement is 0.0.
    """
    return series.fillna(value)


class SyntheticBar:
    """
    Synthetic bar used by the original Pine script.

    Pine source:

        bar.new(
            nz(src[1]),
            math.max(nz(src[1]), src),
            math.min(nz(src[1]), src),
            src
        )

    Here `source_col` is the external indicator input source,
    e.g. close, hl2, or any precomputed column.
    """

    def __init__(self, source: pd.Series):
        prev_source = _nz(source.shift(1))

        self.o = prev_source
        self.h = pd.concat([prev_source, source], axis=1).max(axis=1)
        self.l = pd.concat([prev_source, source], axis=1).min(axis=1)
        self.c = source

    def get_source(self, kind: str) -> pd.Series:
        if kind == "oc2":
            return (self.o + self.c) / 2.0
        if kind == "hl2":
            return (self.h + self.l) / 2.0
        if kind == "hlc3":
            return (self.h + self.l + self.c) / 3.0
        if kind == "ohlc4":
            return (self.o + self.h + self.l + self.c) / 4.0
        if kind == "hlcc4":
            return (self.h + self.l + self.c + self.c) / 4.0

        raise ValueError(f"Unsupported synthetic source kind: {kind}")

    def atr(self, length: int) -> pd.Series:
        if length < 1:
            raise ValueError("length must be >= 1")

        prev_h = self.h.shift(1)
        prev_c = self.c.shift(1)

        tr_first = self.h - self.l

        tr_normal = pd.concat(
            [
                self.h - self.l,
                (self.h - prev_c).abs(),
                (self.l - prev_c).abs(),
            ],
            axis=1,
        ).max(axis=1)

        tr = tr_normal.where(prev_h.notna(), tr_first)

        if length == 1:
            return tr

        return rma(tr, length)

    def supertrend(self, factor: float, length: int) -> tuple[pd.Series, pd.Series]:
        atr = self.atr(length)

        hl2 = self.get_source("hl2")

        basic_up = hl2 + factor * atr
        basic_dn = hl2 - factor * atr

        n = len(self.c)

        final_up = np.full(n, np.nan, dtype=float)
        final_dn = np.full(n, np.nan, dtype=float)
        st_value = np.full(n, np.nan, dtype=float)
        st_direction = np.full(n, np.nan, dtype=float)

        close_values = self.c.to_numpy(dtype=float)
        atr_values = atr.to_numpy(dtype=float)
        basic_up_values = basic_up.to_numpy(dtype=float)
        basic_dn_values = basic_dn.to_numpy(dtype=float)

        for i in range(n):
            up = basic_up_values[i]
            dn = basic_dn_values[i]

            prev_up = final_up[i - 1] if i > 0 else np.nan
            prev_dn = final_dn[i - 1] if i > 0 else np.nan
            prev_st = st_value[i - 1] if i > 0 else np.nan
            prev_dir = st_direction[i - 1] if i > 0 else np.nan
            prev_close = close_values[i - 1] if i > 0 else np.nan
            prev_atr = atr_values[i - 1] if i > 0 else np.nan

            # Pine:
            # up := up < nz(up[1]) or b.c[1] > nz(up[1]) ? up : nz(up[1])
            nz_prev_up = 0.0 if np.isnan(prev_up) else prev_up
            if up < nz_prev_up or prev_close > nz_prev_up:
                final_up[i] = up
            else:
                final_up[i] = nz_prev_up

            # Pine:
            # dn := dn > nz(dn[1]) or b.c[1] < nz(dn[1]) ? dn : nz(dn[1])
            nz_prev_dn = 0.0 if np.isnan(prev_dn) else prev_dn
            if dn > nz_prev_dn or prev_close < nz_prev_dn:
                final_dn[i] = dn
            else:
                final_dn[i] = nz_prev_dn

            # Pine:
            # dir := switch
            #     na(atr[1])         => 1
            #     st[1] == nz(up[1]) => b.c > up ? -1 : +1
            #     =>                    b.c < dn ? +1 : -1
            if np.isnan(prev_atr):
                direction = 1.0
            elif prev_st == nz_prev_up:
                direction = -1.0 if close_values[i] > final_up[i] else 1.0
            else:
                direction = 1.0 if close_values[i] < final_dn[i] else -1.0

            st_direction[i] = direction

            # Pine:
            # st := dir == -1 ? dn : up
            st_value[i] = final_dn[i] if direction == -1.0 else final_up[i]

        st_value_series = pd.Series(st_value, index=self.c.index, name="st_value")
        st_direction_series = pd.Series(st_direction, index=self.c.index, name="st_direction").astype("Int64")

        return st_value_series, st_direction_series


def add_super_trend(
    df: pd.DataFrame,
    length: int = 10,
    factor: float = 5.0,
    source: str = "close",
    value_col: str = "st_value",
    direction_col: str = "st_direction",
) -> pd.DataFrame:
    """
    Add SuperTrend Period+ columns translated from Pine Script.

    Output columns:
        - value_col: SuperTrend line value, equivalent to Pine st.s
        - direction_col: SuperTrend direction, equivalent to Pine st.d

    Time protocol:
        st_value[t] and st_direction[t] only depend on rows[:t+1].
    """
    if source not in df.columns:
        raise ValueError(f"source column not found: {source}")

    out = df.copy()
    source_series = pd.to_numeric(out[source], errors="coerce")

    synthetic_bar = SyntheticBar(source_series)
    st_value, st_direction = synthetic_bar.supertrend(factor=factor, length=length)

    out[value_col] = st_value
    out[direction_col] = st_direction

    return out