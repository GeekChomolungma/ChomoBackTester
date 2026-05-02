from pathlib import Path

import pandas as pd
import mplfinance as mpf


def load_vol_band_csv(csv_path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    required = [
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "reversal_upper",
        "reversal_lower",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "reversal_upper",
        "reversal_lower",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("datetime").reset_index(drop=True)
    df = df.set_index("datetime")

    df = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )

    return df


def plot_volatility_band(
    csv_path: str | Path,
    output_path: str | Path | None = None,
    title: str | None = None,
    max_rows: int | None = None,
    show_volume: bool = False,
    show_grid: bool = True,
    theme: str = "light",
) -> None:
    df = load_vol_band_csv(csv_path)

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

    market_colors = mpf.make_marketcolors(
        up="#00c176",
        down="#ff3b30",
        edge="inherit",
        wick="inherit",
        volume="inherit",
    )

    if theme == "dark":
        style = mpf.make_mpf_style(
            base_mpf_style="nightclouds",
            marketcolors=market_colors,
            gridstyle="-" if show_grid else "",
            gridcolor="#444444",
        )
    elif theme == "light":
        style = mpf.make_mpf_style(
            base_mpf_style="default",
            marketcolors=market_colors,
            gridstyle="-" if show_grid else "",
            gridcolor="#e6e6e6",
            facecolor="white",
            edgecolor="black",
            rc={
                "axes.labelcolor": "black",
                "xtick.color": "black",
                "ytick.color": "black",
            },
        )
    else:
        raise ValueError("theme must be 'light' or 'dark'")

    savefig = None
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        savefig = dict(fname=str(output_path), dpi=150, bbox_inches="tight")

    mpf.plot(
        df,
        type="candle",
        style=style,
        addplot=add_plots,
        volume=show_volume,
        title=title or "Volatility Reversion Bands Visualization",
        ylabel="Price",
        figsize=(16, 8),
        warn_too_much_data=10000,
        savefig=savefig,
    )


if __name__ == "__main__":
    plot_volatility_band(
        csv_path="../output/btc/BTCUSDT_1d_Binance_with_indicators.csv",
        output_path="figs/BTCUSDT_1d_volatility_band.png",
        max_rows=300,
        show_volume=False,
        show_grid=True,
        theme="light",
    )