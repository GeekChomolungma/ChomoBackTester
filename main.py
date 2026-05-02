from pathlib import Path

from core.kline_loader import load_and_standardize_kline
from indicators import apply_indicator


INPUT_ROOT = Path("market_info")
OUTPUT_ROOT = Path("output")


INDICATOR_PIPELINE = [
    {
        "name": "super_trend",
        "params": {
            "length": 14,
            "factor": 5.0,
            "source": "close",
            "value_col": "st_value",
            "direction_col": "st_direction",
        },
    },
    {
        "name": "volatility_band",
        "params": {
            "length": 20,
            "mult": 2.0,
            "atr_mult": 1.5,
            "source": "close",
            "upper_col": "reversal_upper",
            "lower_col": "reversal_lower",
        },
    },
    # 后续继续加：
    # {
    #     "name": "rsi",
    #     "params": {
    #         "length": 14,
    #         "source": "close",
    #         "output_col": "rsi_14",
    #     },
    # },
]


def apply_indicator_pipeline(df, pipeline: list[dict]):
    out = df.copy()

    for item in pipeline:
        name = item["name"]
        params = item.get("params", {})

        print(f"  Applying indicator: {name}")
        out = apply_indicator(out, name, **params)

    return out


def process_one_file(csv_path: Path, pipeline: list[dict]):
    df = load_and_standardize_kline(csv_path)

    df = apply_indicator_pipeline(df, pipeline)

    relative_path = csv_path.relative_to(INPUT_ROOT)
    output_dir = OUTPUT_ROOT / relative_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{csv_path.stem}_with_indicators.csv"
    df.to_csv(output_path, index=False)

    print(f"Saved: {output_path}")


def main():
    csv_files = sorted(INPUT_ROOT.glob("btc/*.csv"))

    for csv_path in csv_files:
        print(f"Processing: {csv_path}")
        process_one_file(csv_path, INDICATOR_PIPELINE)


if __name__ == "__main__":
    main()