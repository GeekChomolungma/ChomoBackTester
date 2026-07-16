"""
Grid search over st_vrb_enhanced's two touch thresholds
(st_touch_pct, vrb_touch_pct). Run from the repo root:

    python -m optimize.sweeps.st_vrb_enhanced.touch
"""

from pathlib import Path

from datasource.kline_loader import load_and_standardize_kline
from optimize.date_window import slice_with_lookback
from optimize.grid_search import run_grid_search
from optimize.visualize import plot_heatmap
from strategy import build_enriched, get_strategy

INPUT_FILE = Path("market_info/zec/ZECUSDT_4h_Binance.csv")
OUTPUT_DIR = Path("output/optimize/st_vrb_enhanced/touch/zec")

START_DATE = "2026-04-05"
END_DATE = None

FIXED_OVERRIDES = {
    "st_length": 24,
    "st_factor": 5.0,
    "vb_length": 24,
    "vb_mult": 2.5,
    "vb_atr_mult": 1,
    "use_short": True,
    "take_profit_pct": 0.05,
    "stop_loss_pct": 0.03,
}

PARAM_GRID = {
    "st_touch_pct": [round(0.01 * i, 2) for i in range(1, 11)],
    "vrb_touch_pct": [round(0.01 * i, 2) for i in range(1, 11)],
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
    strategy = get_strategy("st_vrb_enhanced")

    enriched_full = build_enriched(df, strategy, FIXED_OVERRIDES)
    enriched_window = slice_with_lookback(
        enriched_full, start=START_DATE, end=END_DATE, lookback_bars=1
    )

    results = run_grid_search(
        enriched_window,
        strategy,
        PARAM_GRID,
        base_params=FIXED_OVERRIDES,
        rebuild_indicators=False,
        report_start=START_DATE,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results_path = OUTPUT_DIR / f"{INPUT_FILE.stem}_touch_grid_results.csv"
    results.to_csv(results_path, index=False)
    print(f"Saved grid search results: {results_path}")

    for metric in METRICS:
        heatmap_path = plot_heatmap(
            results,
            x_param="st_touch_pct",
            y_param="vrb_touch_pct",
            metric=metric,
            out_path=OUTPUT_DIR / f"{INPUT_FILE.stem}_{metric}_heatmap.png",
        )
        print(f"Saved heatmap: {heatmap_path}")


if __name__ == "__main__":
    main()
