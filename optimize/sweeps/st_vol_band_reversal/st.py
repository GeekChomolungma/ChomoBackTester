"""
Full param sweep (st_length x st_factor) for the st_vol_band_reversal
strategy, using the general-purpose optimize.grid_search.run_grid_search
(indicators are recomputed for every combo, since st_length/st_factor
feed build_indicators). Copy this file under optimize/sweeps/ as a
starting point for a new strategy's sweep -- swap PARAM_GRID / INPUT_FILE
/ strategy name / metric names. Run as a module from the repo root
(needed so the top-level datasource/strategy/backtest/optimize packages
resolve):

    python -m optimize.sweeps.st_vol_band_reversal.st
"""

from pathlib import Path

from datasource.kline_loader import load_and_standardize_kline
from optimize.grid_search import run_grid_search
from optimize.visualize import plot_bar_ranking, plot_heatmap
from strategy import get_strategy

INPUT_FILE = Path("market_info/ltc/LTCUSDT_4h_Binance.csv")
OUTPUT_DIR = Path("output/optimize/st_vol_band_reversal/st")

PARAM_GRID = {
    "st_length": [7, 10, 14, 21],
    "st_factor": [2.0, 3.0, 5.0, 7.0],
}


def main():
    df = load_and_standardize_kline(INPUT_FILE)
    strategy = get_strategy("st_vol_band_reversal")

    results = run_grid_search(df, strategy, PARAM_GRID)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results_path = OUTPUT_DIR / f"{INPUT_FILE.stem}_grid_results.csv"
    results.to_csv(results_path, index=False)
    print(f"Saved grid search results: {results_path}")

    heatmap_path = plot_heatmap(
        results,
        x_param="st_length",
        y_param="st_factor",
        metric="profit_factor",
        out_path=OUTPUT_DIR / f"{INPUT_FILE.stem}_profit_factor_heatmap.png",
    )
    print(f"Saved heatmap: {heatmap_path}")

    ranking_path = plot_bar_ranking(
        results,
        metric="net_pnl",
        out_path=OUTPUT_DIR / f"{INPUT_FILE.stem}_net_pnl_ranking.png",
    )
    print(f"Saved ranking chart: {ranking_path}")


if __name__ == "__main__":
    main()
