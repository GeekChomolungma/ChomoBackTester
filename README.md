# ChomoBackTester

A cryptocurrency strategy backtesting and parameter optimization framework. It ingests raw Binance
candlestick CSV data, enriches it with TradingView-compatible technical indicators, runs pluggable
trading strategies on top of that enriched time series to mark buy/sell events, computes standard
backtest performance metrics from those events, and sweeps strategy/indicator parameters to find
what works.

> This repo started as a pure K-line preprocessing library (load → indicator pipeline → enriched
> CSV/parquet). That layer still exists unchanged (`datasource/`, `indicators/`, `fin_features/`) —
> it's now the foundation `strategy/` builds on.

---

## Architecture

```text
kline-preprocess/
├── datasource/                  # Data ingestion — CSV today, Mongo/MySQL loaders land here later
│   └── kline_loader.py          # CSV ingestion and standardization (unchanged)
├── indicators/                  # Technical indicator registry & pipeline dispatcher (unchanged)
│   ├── ta_utils.py              # Shared TA primitives (SMA, RMA, ATR, …)
│   ├── super_trend.py           # SuperTrend Period+ indicator
│   ├── volatility_band.py       # Volatility Reversion Bands indicator
│   ├── rsi.py                   # RSI indicator
│   └── pine_files/              # Original Pine Script source files (reference)
├── fin_features/                # Non-indicator time series features, e.g. log_return (unchanged)
├── strategy/                    # Trading strategies — each one wires up the indicators/
│   │                            # features it needs and decides when to buy/sell
│   ├── base.py                  # Strategy contract (dataclass)
│   └── st_vol_band_reversal.py  # Sample strategy: SuperTrend flip-and-reverse
├── backtest/                    # Strategy-agnostic performance metrics library
│   ├── trades.py                # signal column -> trade list
│   └── metrics.py                # trade list -> Net PnL / Sharpe / win rate / profit factor / …
├── optimize/                    # Parameter sweeps + visualization
│   ├── grid_search.py           # param grid -> results DataFrame (one row per combo)
│   ├── visualize.py             # heatmap / ranking bar chart, saved as PNG
│   └── example_grid_search.py   # runnable template — copy & adapt for your own strategy
├── market_info/                 # Input data directory (Binance K-line CSVs), {symbol}/ per pair
├── output/                      # Generated output (auto-created)
│   ├── {strategy_name}/{symbol}/       # enriched+signals CSV, trade list, metrics
│   └── optimize/{strategy_name}/       # grid search results CSV + PNG charts
├── visual_test/                 # Ad-hoc indicator chart visualizations
└── run_backtest.py              # Entry point: run one strategy across a batch of K-line files
```

### How indicators, strategies, and backtest fit together

1. **indicators/** and **fin_features/** are plugin registries. Each one is a pure function
   `(df, **params) -> df` that adds columns aligned 1:1 with the OHLCV time series, and must be
   *causal* — `indicator[t]` may only depend on `rows[:t+1]` (see the no-lookahead protocol at the
   top of `indicators/__init__.py`). New indicators just get added here and registered.

2. **strategy/** is where indicators get combined into a trading decision. A `Strategy` (see
   `strategy/base.py`) bundles:
   - `build_indicators(params) -> list[dict]` — which indicators to apply and with what params
   - `build_features(params) -> list[dict]` — same, for `fin_features`
   - `generate_signals(df, params) -> df` — reads the enriched df and writes a sparse `signal`
     column
   - `params` — the strategy's default flat param dict (indicator params + strategy-only params
     live together here, so an optimizer can sweep both through one interface)

   `strategy.run_strategy(df, strategy)` runs the whole thing: build the enriched df, then call
   `generate_signals`, returning one DataFrame with OHLCV + indicator columns + `signal`.

3. **Signal convention**: `signal` is mostly `NaN`. A row only gets a value when a trade actually
   executes on that bar, using one of `long_entry` / `long_exit` / `short_entry` / `short_exit`
   (comma-joined if a reversal closes one side and opens the other on the same bar, e.g.
   `short_exit,long_entry`). To stay causal, a decision made from data through bar `t` is *written
   and filled on bar `t+1`* (using `open[t+1]` as the fill price) — never on the bar that produced
   it. This means `backtest/trades.py` can read `signal` directly as "the bar this trade filled on"
   with no offset logic of its own.

4. **backtest/** only consumes the enriched+signal DataFrame — it doesn't know or care which
   strategy produced it. `extract_trades(df)` walks `signal` and reconstructs a trade list (entry
   price/time, exit price/time, pnl, return %, bars held, open/closed status). `compute_metrics(trades)`
   turns that into a metrics dict: trade count, win rate, net PnL, gross profit/loss, profit factor,
   average win/loss, largest win/loss, max drawdown, Sharpe/Sortino (per-trade, not annualized —
   see the docstring in `backtest/metrics.py`), and max consecutive win/loss streaks.

5. **optimize/** drives `strategy` + `backtest` across a parameter grid. `run_grid_search(df,
   strategy, param_grid)` sweeps every combination in `param_grid` (any key from the strategy's flat
   `params`, indicator or strategy-level) and returns one row of `{params..., metrics...}` per
   combination. `visualize.py` turns that into a heatmap (two swept params vs. one metric) or a
   ranked bar chart (top N combos by a metric).

---

## Quick Start

### 1. Install dependencies

```bash
pip install pandas numpy pyarrow matplotlib mplfinance
```

### 2. Prepare input data

Place Binance K-line CSV files under `market_info/{symbol}/`, e.g. `market_info/btc/BTCUSDT_1d_Binance.csv`.
Each CSV must contain: `starttime`, `open`, `high`, `low`, `close`, `volume`, `symbol`, `interval`.

### 3. Run a strategy backtest

```bash
python run_backtest.py
```

Defaults to the sample `st_vol_band_reversal` strategy over `market_info/ltc/*.csv`. For each file
this writes to `output/{strategy_name}/{symbol}/`:

- `{file}_enriched_signals.csv` — OHLCV + indicator columns + `signal`
- `{file}_trades.csv` — reconstructed trade list
- `{file}_metrics.csv` — one-row metrics summary

To run a different symbol or strategy, edit `INPUT_ROOT.glob(...)` / `STRATEGY_NAME` in
`run_backtest.py`.

### 4. Run a parameter sweep

```bash
python -m optimize.example_grid_search
```

Sweeps `st_length` × `st_factor` for the sample strategy, and writes a results CSV plus a
profit-factor heatmap and a net-PnL ranking chart to `output/optimize/{strategy_name}/`. Copy this
file and swap in your own `PARAM_GRID` / strategy / metric to build a new sweep.

---

## Adding a new strategy

1. Create `strategy/my_strategy.py`. Define `build_indicators(params)`, optionally
   `build_features(params)`, and `generate_signals(df, params)` (write only to a sparse `signal`
   column, respecting the t → t+1 execution offset described above).
2. Export a module-level `STRATEGY = Strategy(name=..., build_indicators=..., generate_signals=...,
   params={...})`.
3. Register it in `STRATEGY_REGISTRY` in `strategy/__init__.py`.
4. Point `run_backtest.py` / your own script at it via `get_strategy("my_strategy")`.

## Adding a new indicator

Unchanged from before — add a module under `indicators/`, implement `add_my_indicator(df, **params)
-> df` following the no-lookahead protocol, and register it in `INDICATOR_REGISTRY` in
`indicators/__init__.py`. Any strategy can then reference it by name in `build_indicators`.

---

## Indicators (unchanged)

### SuperTrend Period+

- **Default params**: `length=14, factor=5.0, source='close'`
- **Output**: `st_value` (price line), `st_direction` (`-1` = bullish, `1` = bearish)

### Volatility Reversion Bands

- **Default params**: `length=20, mult=2.0, atr_mult=1.5, source='close'`
- **Output**: `reversal_upper`, `reversal_lower`

### RSI

- **Default params**: `length=14, source='close'`
- **Output**: `rsi_{length}`

---

## Data

Sample data sourced from Binance, covering 6 symbols × 4 timeframes, from 2017 to 2026 (UTC):

| Symbol                        | Timeframes           |
|-------------------------------|-----------------------|
| BTC, ETH, LTC, XRP, BCH, BNB  | 15m / 1h / 4h / 1d   |

Files are organized as `market_info/{symbol}/{SYMBOL}{interval}_Binance.csv`.

**Download**: [Google Drive](https://drive.google.com/file/d/11J7LR7qp3cVVwsJgQmsWuiw3Tge-QVFV/view)
