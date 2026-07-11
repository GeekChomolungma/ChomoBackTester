"""
Run as a module from the repo root (needed for the top-level packages to
resolve): python -m visual_tools.st_visual
"""

from pathlib import Path

import mplfinance as mpf

from visual_tools.style import load_ohlcv_csv, make_mpf_style, savefig_kwargs


def plot_super_trend(
    csv_path: str | Path,
    output_path: str | Path | None = None,
    title: str | None = None,
    max_rows: int | None = None,
    show_volume: bool = False,
    show_grid: bool = False,
    theme: str = "light",
) -> None:
    df = load_ohlcv_csv(csv_path, extra_numeric_cols=("st_value", "st_direction"))

    if max_rows is not None:
        df = df.tail(max_rows)

    # ===== SuperTrend 分离 =====
    bear_st = df["st_value"].where(df["st_direction"] > 0)
    bull_st = df["st_value"].where(df["st_direction"] < 0)

    add_plots = [
        mpf.make_addplot(bear_st, color="#ff4800", width=1.2),
        mpf.make_addplot(bull_st, color="#008cff", width=1.2),
    ]

    mpf.plot(
        df,
        type="candle",
        style=make_mpf_style(theme=theme, show_grid=show_grid),
        addplot=add_plots,
        volume=show_volume,
        title=title or "SuperTrend Period+ Visualization",
        ylabel="Price",
        figsize=(16, 8),
        warn_too_much_data=10000,
        savefig=savefig_kwargs(output_path),
    )


if __name__ == "__main__":
    plot_super_trend(
        csv_path="output/st_vrb_clean/btc/BTCUSDT_4h_Binance_enriched_signals.csv",
        output_path="visual_tools/figs/BTCUSDT_4h_super_trend.png",
        max_rows=300,
        show_volume=False,
        show_grid=True,
    )
