from pathlib import Path

from core.kline_loader import load_and_standardize_kline
from indicators import apply_indicator
from fin_features import apply_feature


INPUT_ROOT = Path("market_info")
OUTPUT_ROOT = Path("output")

# ================ Financial Feature Pipeline ================

FEATURE_PIPELINE = [
    {
        "name": "log_return",
        "params": {
            "source": "close",
            "output_col": "target_logreturn",
        },
    },
]

def apply_feature_pipeline(df, pipeline: list[dict]):
    out = df.copy()

    for item in pipeline:
        name = item["name"]
        params = item.get("params", {})

        print(f"  Applying feature: {name}")
        out = apply_feature(out, name, **params)

    return out


# ================ Technical Indicator Pipeline ================

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


# ================ Main Process ================

def process_one_file(csv_path: Path):
    df = load_and_standardize_kline(csv_path)

    df = apply_feature_pipeline(df, FEATURE_PIPELINE)
    df = apply_indicator_pipeline(df, INDICATOR_PIPELINE)

    relative_path = csv_path.relative_to(INPUT_ROOT)
    output_dir = OUTPUT_ROOT / relative_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # === CSV output ===
    csv_path_out = output_dir / f"{csv_path.stem}_with_indicators.csv"
    df.to_csv(csv_path_out, index=False)

    # === Parquet output ===
    parquet_path_out = output_dir / f"{csv_path.stem}_with_indicators.parquet"
    df.to_parquet(parquet_path_out, index=False, engine="pyarrow")

    print(f"Saved CSV: {csv_path_out}")
    print(f"Saved Parquet: {parquet_path_out}")


def main():
    csv_files = sorted(INPUT_ROOT.glob("eth/*.csv"))

    for csv_path in csv_files:
        print(f"Processing: {csv_path}")
        process_one_file(csv_path)


if __name__ == "__main__":
    main()