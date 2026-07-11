"""
Run as a module from the repo root (needed for the top-level packages to
resolve): python -m visual_tools.backtest_visual
"""

from pathlib import Path

import numpy as np
import pandas as pd
import mplfinance as mpf

from visual_tools.style import load_ohlcv_csv, make_mpf_style, savefig_kwargs

# Overlaid only if present -- keeps this generic across strategies that use
# a different indicator subset (or none at all).
OPTIONAL_INDICATOR_COLS = ("st_value", "st_direction", "reversal_upper", "reversal_lower")

EVENT_STYLE = {
    "long_entry": dict(marker="^", color="#00c176", markersize=90),
    "long_exit": dict(marker="x", color="#00c176", markersize=70),
    "short_entry": dict(marker="v", color="#ff3b30", markersize=90),
    "short_exit": dict(marker="x", color="#ff3b30", markersize=70),
}


def _event_markers(df: pd.DataFrame) -> dict[str, pd.Series]:
    """
    Rebuild long/short entry/exit marker series from the sparse `signal`
    column, using `Open` as the fill price -- the same convention
    backtest.trades.extract_trades uses (signal is written on the bar it
    actually fills on, see strategy/base.py).
    """
    markers = {event: pd.Series(np.nan, index=df.index) for event in EVENT_STYLE}

    for idx, sig in df["signal"].items():
        if pd.isna(sig):
            continue
        for event in str(sig).split(","):
            if event in markers:
                markers[event].loc[idx] = df.loc[idx, "Open"]

    return markers


def plot_backtest(
    csv_path: str | Path,
    output_path: str | Path | None = None,
    title: str | None = None,
    max_rows: int | None = None,
    show_volume: bool = False,
    show_grid: bool = True,
    theme: str = "light",
) -> None:
    """
    Plot candles + whichever indicator overlays are present + long/short
    entry/exit markers, from a strategy's `*_enriched_signals.csv` (the
    file run_backtest.py writes per strategy/symbol).
    """
    df = load_ohlcv_csv(
        csv_path,
        optional_numeric_cols=OPTIONAL_INDICATOR_COLS,
        passthrough_cols=("signal",),
    )

    if max_rows is not None:
        df = df.tail(max_rows)

    add_plots = []

    if "st_value" in df.columns and "st_direction" in df.columns:
        bear_st = df["st_value"].where(df["st_direction"] > 0)
        bull_st = df["st_value"].where(df["st_direction"] < 0)
        add_plots.append(mpf.make_addplot(bear_st, color="#ff4800", width=1.2))
        add_plots.append(mpf.make_addplot(bull_st, color="#008cff", width=1.2))

    if "reversal_upper" in df.columns and "reversal_lower" in df.columns:
        add_plots.append(mpf.make_addplot(df["reversal_upper"], color="#e40df3", width=1.0))
        add_plots.append(mpf.make_addplot(df["reversal_lower"], color="#04ddd2", width=1.0))

    for event, series in _event_markers(df).items():
        if series.notna().sum() == 0:
            continue
        style = EVENT_STYLE[event]
        add_plots.append(
            mpf.make_addplot(
                series,
                type="scatter",
                markersize=style["markersize"],
                marker=style["marker"],
                color=style["color"],
            )
        )

    mpf.plot(
        df,
        type="candle",
        style=make_mpf_style(theme=theme, show_grid=show_grid),
        addplot=add_plots,
        volume=show_volume,
        title=title or "Backtest Visualization",
        ylabel="Price",
        figsize=(18, 9),
        warn_too_much_data=10000,
        savefig=savefig_kwargs(output_path),
    )


if __name__ == "__main__":
    plot_backtest(
        csv_path="output/st_vrb_clean/zec/ZECUSDT_4h_Binance_enriched_signals.csv",
        output_path="visual_tools/figs/ZECUSDT_4h_st_vrb_clean.png",
        max_rows=300,
        show_volume=False,
        show_grid=True,
        theme="light",
    )
