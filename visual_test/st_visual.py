from pathlib import Path

import pandas as pd
import mplfinance as mpf


def load_st_csv(csv_path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    required = [
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "st_value",
        "st_direction",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for col in ["open", "high", "low", "close", "volume", "st_value"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["st_direction"] = pd.to_numeric(df["st_direction"], errors="coerce")

    df = df.sort_values("datetime").reset_index(drop=True)
    df = df.set_index("datetime")

    # mplfinance requires capitalized OHLCV column names
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


def plot_super_trend(
    csv_path: str | Path,
    output_path: str | Path | None = None,
    title: str | None = None,
    max_rows: int | None = None,
    show_volume: bool = False,
    show_grid: bool = False,
) -> None:
    df = load_st_csv(csv_path)

    if max_rows is not None:
        df = df.tail(max_rows)

    # ===== SuperTrend 分离 =====
    bear_st = df["st_value"].where(df["st_direction"] > 0)
    bull_st = df["st_value"].where(df["st_direction"] < 0)

    add_plots = [
        mpf.make_addplot(bear_st, color="#ff4800", width=1.2),
        mpf.make_addplot(bull_st, color="#008cff", width=1.2),
    ]

    # ===== K线颜色（接近 TradingView）=====
    market_colors = mpf.make_marketcolors(
        up="#00c176",
        down="#ff3b30",
        edge="inherit",
        wick="inherit",
        volume="inherit",
    )

    # ===== Grid 控制 =====
    gridstyle = "-" if show_grid else ""

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
        }
    )

    # ===== 保存控制 =====
    savefig = None
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        savefig = dict(fname=str(output_path), dpi=150, bbox_inches="tight")

    # ===== 绘图 =====
    mpf.plot(
        df,
        type="candle",
        style=style,
        addplot=add_plots,
        volume=show_volume,  # ← 控制 volume
        title=title or "SuperTrend Period+ Visualization",
        ylabel="Price",
        figsize=(16, 8),
        warn_too_much_data=10000,
        savefig=savefig,
    )


if __name__ == "__main__":
    plot_super_trend(
        csv_path="../output/btc/BTCUSDT_1d_Binance_with_indicators.csv",
        output_path="figs/BTCUSDT_1d_super_trend.png",
        max_rows=300,
        show_volume=False,
        show_grid=True,
    )