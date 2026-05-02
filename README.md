# kline-preprocess

A cryptocurrency K-line preprocessing library that ingests raw Binance candlestick CSV data, applies TradingView-compatible technical indicators, and outputs enriched CSVs ready for Deeplearning train and infer.

---

## Features

- Load and standardize Binance K-line CSV exports
- Implement TradingView Pine Script indicators with strict **no-lookahead** guarantees
- Output enriched CSVs containing original OHLCV columns plus indicator columns

---

## Project Structure

```
kline-preprocess/
├── core/
│   └── kline_loader.py         # CSV ingestion and standardization
├── indicators/
│   ├── __init__.py             # Indicator registry & pipeline dispatcher
│   ├── ta_utils.py             # Shared TA primitives (SMA, RMA, ATR, …)
│   ├── super_trend.py          # SuperTrend Period+ indicator
│   ├── volatility_band.py      # Volatility Reversion Bands indicator
│   ├── rsi.py                  # RSI indicator
│   └── pine_files/             # Original Pine Script source files (reference)
├── market_info/                # Input data directory (Binance K-line CSVs)
│   └── {symbol}/               # One subdirectory per symbol, e.g. btc/ eth/
├── output/                     # Generated output directory (auto-created)
│   └── {symbol}/               # Mirrors input directory structure
├── visual_test/
│   ├── st_visual.py            # SuperTrend chart visualization
│   └── volBand_visual.py       # Volatility Bands chart visualization
└── main.py                     # Entry point — runs the full pipeline
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install pandas numpy mplfinance
```

### 2. Prepare input data

Place Binance K-line CSV files under `market_info/{symbol}/`. Expected filename format:

```
market_info/btc/BTCUSDT_1d_Binance.csv
market_info/eth/ETHUSDT_4h_Binance.csv
```

Each CSV must contain the following columns:

| Column      | Description                                    |
|-------------|------------------------------------------------|
| `starttime` | Bar open time (Unix milliseconds)              |
| `open`      | Open price                                     |
| `high`      | High price                                     |
| `low`       | Low price                                      |
| `close`     | Close price                                    |
| `volume`    | Volume                                         |
| `symbol`    | Trading pair, e.g. `BTCUSDT`                   |
| `interval`  | Timeframe, e.g. `1d` / `4h` / `1h` / `15m`     |

### 3. Run the pipeline

```bash
python main.py
```

Output files are written to `output/{symbol}/`:

```
output/btc/BTCUSDT_1d_Binance_with_indicators.csv
```

---

## Output Format

The output CSV contains the original OHLCV columns plus all configured indicator columns:

| Column                               | Type     | Description                                              |
|--------------------------------------|----------|----------------------------------------------------------|
| `datetime`                           | datetime | Human-readable timestamp converted from `starttime`      |
| `starttime`                          | int64    | Original millisecond timestamp                           |
| `symbol`                             | str      | Trading pair                                             |
| `interval`                           | str      | Timeframe                                                |
| `open / high / low / close / volume` | float64  | Original OHLCV                                           |
| `st_value`                           | float64  | SuperTrend price line                                    |
| `st_direction`                       | Int64    | SuperTrend direction. `-1` = bullish, `1` = bearish      |
| `reversal_upper`                     | float64  | Volatility Band upper rail (resistance reversal level)   |
| `reversal_lower`                     | float64  | Volatility Band lower rail (support reversal level)      |

> Rows within the indicator warm-up period have `NaN` in indicator columns.

---

## Indicators

### SuperTrend Period+

- **Source**: TradingView Pine Script v5
- **Default params**: `length=14, factor=5.0, source='close'`
- **Output**: `st_value` (price line), `st_direction` (trend direction)
- **Note**: Reconstructs synthetic OHLC bars to match Pine Script behavior exactly

### Volatility Reversion Bands

- **Source**: TradingView Pine Script v6
- **Default params**: `length=20, mult=2.0, atr_mult=1.5, source='close'`
- **Output**: `reversal_upper` (upper rail), `reversal_lower` (lower rail)
- **Algorithm**: Bollinger Band midline ± standard deviation ± ATR adjustment — marks extreme reversal zones

### RSI (implemented, disabled by default)

- **Default params**: `length=14, source='close'`
- **Output**: `rsi_{length}`
- **To enable**: uncomment lines 35–41 in `main.py`

---

## Data

Sample data sourced from Binance, covering 6 symbols × 4 timeframes, from 2017 to 2026 (all timestamps in UTC):

| Symbol                        | Timeframes          |
|-------------------------------|---------------------|
| BTC, ETH, LTC, XRP, BCH, BNB | 15m / 1h / 4h / 1d |

Files are organized as `market_info/{symbol}/{SYMBOL}{interval}_Binance.csv`. Each CSV contains the full set of Binance K-line fields (starttime, OHLCV, symbol, interval, etc.).

**Download**: [Google Drive](https://drive.google.com/file/d/11J7LR7qp3cVVwsJgQmsWuiw3Tge-QVFV/view)
