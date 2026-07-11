from pathlib import Path

import mplfinance as mpf
import pandas as pd

OHLCV_RENAME = {
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume",
}


def load_ohlcv_csv(
    csv_path: str | Path,
    extra_numeric_cols: tuple[str, ...] = (),
    optional_numeric_cols: tuple[str, ...] = (),
    passthrough_cols: tuple[str, ...] = (),
) -> pd.DataFrame:
    """
    Shared loader for the enriched/indicator CSVs written under output/.
    Coerces OHLCV + `extra_numeric_cols` (required) + whichever of
    `optional_numeric_cols` are present to numeric, carries `passthrough_cols`
    through unchanged (e.g. the non-numeric `signal` column), sorts by
    datetime, and renames OHLCV to mplfinance's expected capitalized names.
    """
    df = pd.read_csv(csv_path)

    required = ["datetime", "open", "high", "low", "close", "volume", *extra_numeric_cols, *passthrough_cols]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"])

    numeric_cols = ["open", "high", "low", "close", "volume", *extra_numeric_cols]
    numeric_cols += [c for c in optional_numeric_cols if c in df.columns]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("datetime").reset_index(drop=True)
    df = df.set_index("datetime")
    df = df.rename(columns=OHLCV_RENAME)

    return df


def make_mpf_style(theme: str = "light", show_grid: bool = True) -> object:
    market_colors = mpf.make_marketcolors(
        up="#00c176",
        down="#ff3b30",
        edge="inherit",
        wick="inherit",
        volume="inherit",
    )
    gridstyle = "-" if show_grid else ""

    if theme == "dark":
        return mpf.make_mpf_style(
            base_mpf_style="nightclouds",
            marketcolors=market_colors,
            gridstyle=gridstyle,
            gridcolor="#444444",
        )
    if theme == "light":
        return mpf.make_mpf_style(
            base_mpf_style="default",
            marketcolors=market_colors,
            gridstyle=gridstyle,
            gridcolor="#e6e6e6",
            facecolor="white",
            edgecolor="black",
            rc={
                "axes.labelcolor": "black",
                "xtick.color": "black",
                "ytick.color": "black",
            },
        )

    raise ValueError("theme must be 'light' or 'dark'")


def savefig_kwargs(output_path: str | Path | None) -> dict | None:
    if output_path is None:
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return dict(fname=str(output_path), dpi=150, bbox_inches="tight")
