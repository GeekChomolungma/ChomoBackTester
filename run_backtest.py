from pathlib import Path

import pandas as pd

from backtest import compute_metrics, extract_trades
from datasource.kline_loader import load_and_standardize_kline
from strategy import get_strategy, run_strategy

INPUT_ROOT = Path("market_info")
OUTPUT_ROOT = Path("output")

STRATEGY_NAME = "st_vol_band_reversal"


def process_one_file(csv_path: Path, strategy) -> None:
    df = load_and_standardize_kline(csv_path)
    signaled = run_strategy(df, strategy)

    relative_path = csv_path.relative_to(INPUT_ROOT)
    output_dir = OUTPUT_ROOT / strategy.name / relative_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    enriched_path = output_dir / f"{csv_path.stem}_enriched_signals.csv"
    signaled.to_csv(enriched_path, index=False)
    print(f"Saved enriched+signals: {enriched_path}")

    trades = extract_trades(signaled)
    trades_path = output_dir / f"{csv_path.stem}_trades.csv"
    trades.to_csv(trades_path, index=False)
    print(f"Saved trades: {trades_path}")

    metrics = compute_metrics(trades)
    metrics_path = output_dir / f"{csv_path.stem}_metrics.csv"
    pd.DataFrame([metrics]).to_csv(metrics_path, index=False)
    print(f"Saved metrics: {metrics_path}")

    print(
        f"  trades={metrics['total_trades']} win_rate={metrics['win_rate']:.2f}% "
        f"net_pnl={metrics['net_pnl']:.2f} profit_factor={metrics['profit_factor']:.3f}"
    )


def main() -> None:
    strategy = get_strategy(STRATEGY_NAME)
    csv_files = sorted(INPUT_ROOT.glob("ltc/*.csv"))

    for csv_path in csv_files:
        print(f"Processing: {csv_path}")
        process_one_file(csv_path, strategy)


if __name__ == "__main__":
    main()
