"""
Grid search over st_vrb_enhanced's SuperTrend params
(st_length, st_factor). Run from the repo root:

    python -m optimize.sweeps.st_vrb_enhanced.st
"""

from pathlib import Path

import pandas as pd

from datasource.kline_loader import load_and_standardize_kline
from optimize.grid_search import run_grid_search
from optimize.visualize import plot_heatmap
from strategy import get_strategy

INPUT_FILE = Path("market_info/zec/ZECUSDT_4h_Binance.csv")
OUTPUT_DIR = Path("output/optimize/st_vrb_enhanced/st/zec")

START_DATE = "2026-04-05"
END_DATE = None

FIXED_OVERRIDES = {
    "vb_length": 24,
    "vb_mult": 2.5,
    "vb_atr_mult": 1,
    "use_short": True,
    "st_touch_pct": 0.04,    # optional from touch.py
    "vrb_touch_pct": 0.04,   # optional from touch.py
    "take_profit_pct": 0.05, # optional from profit_loss.py
    "stop_loss_pct": 0.02,   # optional from profit_loss.py
}

PARAM_GRID = {
    "st_length": list(range(7, 31)),
    "st_factor": [round(0.5 * i, 1) for i in range(1, 21)],
}

METRICS = [
    "net_pnl_pct",
    "win_rate",
    "max_drawdown_pct",
    "sharpe_ratio",
    "profit_factor",
    "total_trades",
]


def main() -> None:
    df = load_and_standardize_kline(INPUT_FILE)
    if END_DATE is not None:
        df = df[df["datetime"] <= pd.Timestamp(END_DATE)].reset_index(drop=True)

    strategy = get_strategy("st_vrb_enhanced")

    results = run_grid_search(
        df,
        strategy,
        PARAM_GRID,
        base_params=FIXED_OVERRIDES,
        rebuild_indicators=True,
        report_start=START_DATE,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results_path = OUTPUT_DIR / f"{INPUT_FILE.stem}_st_grid_results.csv"
    results.to_csv(results_path, index=False)
    print(f"Saved grid search results: {results_path}")

    for metric in METRICS:
        heatmap_path = plot_heatmap(
            results,
            x_param="st_length",
            y_param="st_factor",
            metric=metric,
            out_path=OUTPUT_DIR / f"{INPUT_FILE.stem}_{metric}_heatmap.png",
        )
        print(f"Saved heatmap: {heatmap_path}")


if __name__ == "__main__":
    main()
