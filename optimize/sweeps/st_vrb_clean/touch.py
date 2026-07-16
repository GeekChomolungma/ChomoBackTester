"""
Grid search over st_vrb_clean's two "touch" thresholds (st_touch_pct,
vrb_touch_pct) on one symbol/interval, over a fixed backtest window, with
every other param held constant. Run as a module from the repo root:

    python -m optimize.sweeps.st_vrb_clean.touch

Copy this file under optimize/sweeps/{strategy_name}/ and swap INPUT_FILE /
FIXED_OVERRIDES / PARAM_GRID / dates to adapt it to a different symbol,
strategy, or param pair.

Since st_touch_pct/vrb_touch_pct only affect generate_signals (not
build_indicators), indicators are built ONCE over the full history (for
correct SuperTrend/VolatilityBand warmup) and reused for every grid combo
via run_grid_search(..., rebuild_indicators=False), instead of being
recomputed per combo like the default rebuild_indicators=True does. The
backtest window itself is carved out afterward with slice_with_lookback +
report_start, so warmup sees full history but reported metrics only
reflect START_DATE..END_DATE.
"""

from pathlib import Path

from datasource.kline_loader import load_and_standardize_kline
from optimize.date_window import slice_with_lookback
from optimize.grid_search import run_grid_search
from optimize.visualize import plot_heatmap
from strategy import build_enriched, get_strategy

INPUT_FILE = Path("market_info/zec/ZECUSDT_4h_Binance.csv")
OUTPUT_DIR = Path("output/optimize/st_vrb_clean/touch/zec")

START_DATE = "2026-04-05"
END_DATE = None  # None = through the latest bar in the data

# Every param except st_touch_pct/vrb_touch_pct, held fixed at the values
# already tuned by hand (see strategy/st_vrb_clean.py DEFAULT_PARAMS).
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
    "st_touch_pct": [round(0.01 * i, 2) for i in range(1, 11)],   # 0.01..0.10
    "vrb_touch_pct": [round(0.01 * i, 2) for i in range(1, 11)],  # 0.01..0.10
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
    strategy = get_strategy("st_vrb_clean")

    enriched_full = build_enriched(df, strategy, FIXED_OVERRIDES)

    # lookback_bars=1: generate_signals compares st_direction[t] against
    # st_direction[t-1] to detect a flip; without one buffer bar before
    # START_DATE, the window's first row has nothing to compare against
    # and could miss a flip that happened right at the boundary.
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
