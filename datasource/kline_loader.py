from pathlib import Path
import pandas as pd


KLINE_COLUMNS = [
    "datetime",
    "starttime",
    "symbol",
    "interval",
    "open",
    "high",
    "low",
    "close",
    "volume",
]


def load_and_standardize_kline(csv_path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    required = ["starttime", "open", "high", "low", "close", "volume", "symbol", "interval"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{csv_path} missing columns: {missing}")

    df = df.copy()

    df["datetime"] = pd.to_datetime(df["starttime"], unit="ms")

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values(["symbol", "interval", "starttime"]).reset_index(drop=True)

    return df[KLINE_COLUMNS]