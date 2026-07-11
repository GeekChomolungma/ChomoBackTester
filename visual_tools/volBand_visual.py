"""
Run as a module from the repo root (needed for the top-level packages to
resolve): python -m visual_tools.volBand_visual
"""

from pathlib import Path

import mplfinance as mpf

from visual_tools.style import load_ohlcv_csv, make_mpf_style, savefig_kwargs


def plot_volatility_band(
    csv_path: str | Path,
    output_path: str | Path | None = None,
    title: str | None = None,
    max_rows: int | None = None,
    show_volume: bool = False,
    show_grid: bool = True,
    theme: str = "light",
) -> None:
    df = load_ohlcv_csv(csv_path, extra_numeric_cols=("reversal_upper", "reversal_lower"))

    if max_rows is not None:
        df = df.tail(max_rows)

    add_plots = [
        mpf.make_addplot(
            df["reversal_upper"],
            color="#e40df3",
            width=1.2,
            label="Reversal Upper",
        ),
        mpf.make_addplot(
            df["reversal_lower"],
            color="#04ddd2",
            width=1.2,
            label="Reversal Lower",
        ),
    ]

    mpf.plot(
        df,
        type="candle",
        style=make_mpf_style(theme=theme, show_grid=show_grid),
        addplot=add_plots,
        volume=show_volume,
        title=title or "Volatility Reversion Bands Visualization",
        ylabel="Price",
        figsize=(16, 8),
        warn_too_much_data=10000,
        savefig=savefig_kwargs(output_path),
    )


if __name__ == "__main__":
    plot_volatility_band(
        csv_path="output/st_vrb_clean/btc/BTCUSDT_4h_Binance_enriched_signals.csv",
        output_path="visual_tools/figs/BTCUSDT_4h_volatility_band.png",
        max_rows=300,
        show_volume=False,
        show_grid=True,
        theme="light",
    )
