"""
Grid search over st_vrb_clean's SuperTrend params (st_length, st_factor)
on one symbol/interval, over a fixed backtest window, with every other
param held constant at the values already tuned by the earlier sweeps
(touch.py, profit_loss.py) -- see the comments
on FIXED_OVERRIDES below. Run as a module from the repo root:

    python -m optimize.sweeps.st_vrb_clean.st

Copy this file under optimize/sweeps/{strategy_name}/ and swap INPUT_FILE /
FIXED_OVERRIDES / PARAM_GRID / dates to adapt it to a different symbol,
strategy, or param pair.

Unlike the touch/profit-loss sweeps, st_length/st_factor DO feed
build_indicators (they're SuperTrend's own params), so this sweep uses
run_grid_search's default rebuild_indicators=True: build_enriched reruns
for every combo on the full, un-sliced history (giving indicators correct
warmup), and only the reported metrics get scoped to
START_DATE..END_DATE via report_start. volatility_band gets recomputed
alongside SuperTrend every combo too even though its own params never
change -- harmless, just simpler than splitting the two indicators apart.
"""

from pathlib import Path

import pandas as pd

from datasource.kline_loader import load_and_standardize_kline
from optimize.grid_search import run_grid_search
from optimize.visualize import plot_heatmap
from strategy import get_strategy

INPUT_FILE = Path("market_info/zec/ZECUSDT_4h_Binance.csv")
OUTPUT_DIR = Path("output/optimize/st_vrb_clean/st/zec")

START_DATE = "2026-04-05"
END_DATE = None  # None = through the latest bar in the data

# Every param except st_length/st_factor, held fixed.
FIXED_OVERRIDES = {
    "vb_length": 24,
    "vb_mult": 2.5,
    "vb_atr_mult": 1,
    "use_short": True,
    "st_touch_pct": 0.05,      # optimal, found by optimize/sweeps/st_vrb_clean/touch.py
    "vrb_touch_pct": 0.02,     # optimal, found by optimize/sweeps/st_vrb_clean/touch.py
    "take_profit_pct": 0.05,   # optimal, found by optimize/sweeps/st_vrb_clean/profit_loss.py
    "stop_loss_pct": 0.03,     # optimal, found by optimize/sweeps/st_vrb_clean/profit_loss.py
}

PARAM_GRID = {
    "st_length": list(range(7, 31)),                        # 7..30, step 1
    "st_factor": [round(0.5 * i, 1) for i in range(1, 21)],  # 0.5..10.0, step 0.5
}

# net_pnl_pct/win_rate/max_drawdown_pct/sharpe_ratio were asked for
# directly (as the dimensionless equivalents of net_pnl/max_drawdown --
# see backtest/metrics.py's INITIAL_CAPITAL-based equity curve);
# profit_factor and total_trades are added on top since a "stable region"
# call needs both a quality signal beyond win_rate alone (profit_factor)
# and a sample-size sanity check (total_trades) -- a flat-looking sharpe
# patch backed by 3 trades isn't a stable region, it's noise.
METRICS = ["net_pnl_pct", "win_rate", "max_drawdown_pct", "sharpe_ratio", "profit_factor", "total_trades"]


def main() -> None:
    df = load_and_standardize_kline(INPUT_FILE)
    # Indicators are causal (never look forward), so it's safe to truncate
    # the tail directly -- unlike START_DATE, which build_enriched still
    # needs real history before to warm up on (handled by report_start
    # trimming the reported window's front only, after generate_signals).
    if END_DATE is not None:
        df = df[df["datetime"] <= pd.Timestamp(END_DATE)].reset_index(drop=True)

    strategy = get_strategy("st_vrb_clean")

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
