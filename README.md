# ChomoBackTester

A cryptocurrency strategy backtesting and parameter optimization framework. It ingests raw Binance
candlestick CSV data, enriches it with TradingView-compatible technical indicators, runs pluggable
trading strategies on top of that enriched time series to mark buy/sell events, computes standard
backtest performance metrics from those events, sweeps strategy/indicator parameters to find what
works, and renders candles + indicators + entry/exit markers so results can be eyeballed, not just
read off a metrics table.

This is a living library: indicators and strategies get added incrementally over time (usually
ported from a TradingView Pine Script prototype — see `pine_files/`), and each new one plugs into
the same `indicators/` → `strategy/` → `backtest/` → `optimize/` / `visual_tools/` pipeline without
the earlier layers needing to change.

> This repo started as a pure K-line preprocessing library (load → indicator pipeline → enriched
> CSV/parquet). That layer still exists unchanged (`datasource/`, `indicators/`, `fin_features/`) —
> it's now the foundation `strategy/` builds on.

---

## Architecture

```text
ChomoBackTester/
├── datasource/                  # Data ingestion — CSV today, Mongo/MySQL loaders land here later
│   └── kline_loader.py          # CSV ingestion and standardization
├── indicators/                  # Technical indicator registry & pipeline dispatcher
│   ├── ta_utils.py              # Shared TA primitives (SMA, RMA, ATR, …)
│   ├── super_trend.py           # SuperTrend Period+ indicator
│   ├── volatility_band.py       # Volatility Reversion Bands indicator
│   └── rsi.py                   # RSI indicator
├── fin_features/                # Non-indicator time series features, e.g. log_return
├── pine_files/                  # Original TradingView Pine Script sources (reference only)
│   ├── indicator/                   # One .txt per indicator in indicators/
│   └── strategy/                    # One .txt per strategy in strategy/ (pre-port prototype)
├── strategy/                    # Trading strategies — each one wires up the indicators/
│   │                            # features it needs and decides when to buy/sell
│   ├── base.py                  # Strategy contract (dataclass)
│   ├── st_vol_band_reversal.py  # Sample strategy: SuperTrend flip-and-reverse
│   └── st_vrb_clean.py          # SuperTrend + Volatility Band, 3-tier signal priority + SL/TP
├── backtest/                    # Strategy-agnostic performance metrics library
│   ├── trades.py                # signal column -> trade list
│   └── metrics.py                # trade list -> Net PnL / Sharpe / win rate / profit factor / …
├── optimize/                    # Parameter sweeps + visualization
│   ├── grid_search.py                       # full param grid -> results DataFrame (recomputes indicators per combo)
│   ├── signal_grid_search.py                # grid over generate_signals-only params (indicators built once, reused)
│   ├── date_window.py                       # slice an enriched df to a backtest window, with lookback for warmup
│   ├── visualize.py                         # heatmap / ranking bar chart, saved as PNG
│   ├── example_grid_search.py               # runnable template: full grid search
│   └── example_st_vrb_clean_touch_grid.py   # runnable template: signal-only grid search over a date window
├── market_info/                 # Input data directory (Binance K-line CSVs), {symbol}/ per pair
├── output/                      # Generated output (auto-created)
│   ├── {strategy_name}/{symbol}/       # enriched+signals CSV, trade list, metrics
│   └── optimize/{strategy_name}/       # grid search results CSV + PNG charts
├── visual_tools/                # Kline + indicator + signal chart visualizations
│   ├── style.py                 # Shared mplfinance loader/style/savefig helpers
│   ├── st_visual.py             # Single-indicator: SuperTrend overlay
│   ├── volBand_visual.py        # Single-indicator: Volatility Reversion Bands overlay
│   └── backtest_visual.py       # Full backtest view: candles + all present indicators + entry/exit markers
├── requirements.txt
└── run_backtest.py              # Entry point: run one strategy across a batch of K-line files
```

### How the pieces fit together

1. **indicators/** and **fin_features/** are plugin registries. Each one is a pure function
   `(df, **params) -> df` that adds columns aligned 1:1 with the OHLCV time series, and must be
   *causal* — `indicator[t]` may only depend on `rows[:t+1]` (see the no-lookahead protocol at the
   top of `indicators/__init__.py`). New indicators just get added here and registered in
   `INDICATOR_REGISTRY`.

2. **strategy/** is where indicators get combined into a trading decision. A `Strategy` (see
   `strategy/base.py`) bundles:
   - `build_indicators(params) -> list[dict]` — which indicators to apply and with what params
   - `build_features(params) -> list[dict]` — same, for `fin_features`
   - `generate_signals(df, params) -> df` — reads the enriched df and writes a sparse `signal`
     column
   - `params` — the strategy's default flat param dict (indicator params + strategy-only params
     live together here, so an optimizer can sweep both through one interface)

   `strategy.run_strategy(df, strategy)` runs the whole thing: build the enriched df
   (`strategy.build_enriched`), then call `generate_signals`, returning one DataFrame with OHLCV +
   indicator columns + `signal`. This flat, unnamespaced param dict trades a bit of readability for
   letting `optimize/` sweep any param — indicator or strategy-level — through one interface; if a
   strategy ever needs two instances of the same indicator, that'll need a namespacing convention
   this design doesn't have yet.

3. **Signal convention**: `signal` is mostly `NaN`. A row only gets a value when a trade actually
   executes on that bar, using one of `long_entry` / `long_exit` / `short_entry` / `short_exit`
   (comma-joined if a reversal closes one side and opens the other on the same bar, e.g.
   `short_exit,long_entry`). To stay causal, a decision made from data through bar `t` is *written
   and filled on bar `t+1`* (using `open[t+1]` as the fill price) — never on the bar that produced
   it. This means `backtest/trades.py` can read `signal` directly as "the bar this trade filled on"
   with no offset logic of its own. Strategies whose entry/exit logic needs running state (open
   position, average entry price, trailing flags, …) implement this offset with a single forward
   pass over the rows: each iteration first applies whatever the *previous* row decided (writing
   into `events[i]`, filled at `open[i]`), then evaluates the current row's own data and only
   updates plain Python variables (never `events[i]` itself) — so what got decided at `row[i]` is
   only ever realized at `row[i+1]`. See `strategy/st_vrb_clean.py`'s `generate_signals` for a
   worked example with stop-loss/take-profit/pyramiding-free position tracking.

4. **backtest/** only consumes the enriched+signal DataFrame — it doesn't know or care which
   strategy produced it. `extract_trades(df)` walks `signal` and reconstructs a trade list (entry
   price/time, exit price/time, pnl, return %, bars held, open/closed status). `compute_metrics(trades)`
   turns that into a metrics dict: trade count, win rate, net PnL, gross profit/loss, profit factor,
   average win/loss, largest win/loss, max drawdown, Sharpe/Sortino (per-trade, not annualized —
   see the docstring in `backtest/metrics.py`), and max consecutive win/loss streaks.

5. **optimize/** drives `strategy` + `backtest` across a parameter grid, two ways:
   - `run_grid_search(df, strategy, param_grid)` — the general case. Recomputes `build_indicators`
     for every combo, so use it when the swept params include indicator params (e.g. `st_length`).
   - `run_signal_grid_search(enriched, strategy, param_grid, base_params, report_start)` — for
     sweeps where every swept key only affects `generate_signals` (e.g. a touch-distance threshold).
     Indicators are built once by the caller and reused across every combo instead of being
     recomputed per combo. Pair it with `date_window.slice_with_lookback` to scope the reported
     backtest to a fixed date window while still giving indicators (and any row[t-1]-comparing
     signal logic) real history to warm up on.

   `visualize.py` turns either result into a heatmap (two swept params vs. one metric) or a ranked
   bar chart (top N combos by a metric).

6. **visual_tools/** is a third, independent consumer of the same `*_enriched_signals.csv` that
   `backtest/` reads — it never imports `strategy` or `backtest`, it just renders whatever columns
   happen to be present (SuperTrend/VolatilityBand overlays if those columns exist, entry/exit
   markers reconstructed from `signal` using the same `open`-price fill convention as
   `backtest/trades.py`). This means a new strategy's output is visualizable for free, with no new
   visualization code, as long as it writes the same `signal` convention.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare input data

Place Binance K-line CSV files under `market_info/{symbol}/`, e.g. `market_info/btc/BTCUSDT_1d_Binance.csv`.
Each CSV must contain: `starttime`, `open`, `high`, `low`, `close`, `volume`, `symbol`, `interval`.

### 3. Run a strategy backtest

```bash
python run_backtest.py
```

Runs `STRATEGY_NAME` over whatever `INPUT_ROOT.glob(...)` matches in `run_backtest.py` (edit both to
point at a different strategy/symbol). For each file this writes to `output/{strategy_name}/{symbol}/`:

- `{file}_enriched_signals.csv` — OHLCV + indicator columns + `signal`
- `{file}_trades.csv` — reconstructed trade list
- `{file}_metrics.csv` — one-row metrics summary

### 4. Visualize a backtest

```bash
python -m visual_tools.backtest_visual
```

Reads a `*_enriched_signals.csv` from step 3 and renders candles + whichever indicator columns are
present + long/short entry/exit markers to a PNG (edit the `csv_path`/`output_path` at the bottom of
`visual_tools/backtest_visual.py`, or import `plot_backtest(...)` directly). `max_rows` controls how
much of the tail to show — the underlying data is never truncated, only the rendered slice is.

### 5. Run a parameter sweep

```bash
python -m optimize.example_grid_search
```

Sweeps `st_length` × `st_factor` for the sample strategy, and writes a results CSV plus a
profit-factor heatmap and a net-PnL ranking chart to `output/optimize/{strategy_name}/`. Copy this
file and swap in your own `PARAM_GRID` / strategy / metric to build a new sweep.

For sweeps over params that only affect signal logic (not indicators), and/or that should be scoped
to a fixed date window, see `optimize/example_st_vrb_clean_touch_grid.py` instead — it builds
indicators once and reuses them across the whole grid.

```bash
python -m optimize.example_st_vrb_clean_touch_grid
```

---

## Adding a new strategy

1. (Optional) Drop the TradingView Pine Script prototype under `pine_files/strategy/`.
2. Create `strategy/my_strategy.py`. Define `build_indicators(params)`, optionally
   `build_features(params)`, and `generate_signals(df, params)` (write only to a sparse `signal`
   column, respecting the t → t+1 execution offset described above).
3. Export a module-level `STRATEGY = Strategy(name=..., build_indicators=..., generate_signals=...,
   params={...})`.
4. Register it in `STRATEGY_REGISTRY` in `strategy/__init__.py`.
5. Point `run_backtest.py` / your own script at it via `get_strategy("my_strategy")`.

## Adding a new indicator

1. (Optional) Drop the TradingView Pine Script prototype under `pine_files/indicator/`.
2. Add a module under `indicators/`, implement `add_my_indicator(df, **params) -> df` following the
   no-lookahead protocol, and register it in `INDICATOR_REGISTRY` in `indicators/__init__.py`. Any
   strategy can then reference it by name in `build_indicators`.

---

## Strategies

### st_vol_band_reversal

SuperTrend flip-and-reverse: on every SuperTrend direction flip, close whatever's open and reverse
into the new direction. Optionally gated (`use_band_filter`) to only reverse when price is also
outside the Volatility Reversion Band on that side.

### st_vrb_clean

Ported from `pine_files/strategy/st_vrb_clean.txt`. Combines the same two indicators with a 3-tier
signal priority instead of a plain flip: (1) SuperTrend direction flip, (2) price touching the
SuperTrend line while direction already favors that side, (3) price touching a Volatility Band
boundary — tier 3 only ever closes a position, it never opens one. Adds a fixed stop-loss and a
take-profit that only applies to tier-1 entries, and an `use_short` switch (short entries reduce to
a plain close when disabled). See the docstring in `strategy/st_vrb_clean.py` for exactly what was
and wasn't ported from the Pine source (alert payloads and position sizing were dropped as out of
scope for this backtester).

---

## Indicators

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

Sample data sourced from Binance (UTC):

| Symbol                       | Timeframes         |
|------------------------------|--------------------|
| BTC, ETH, LTC, XRP, BCH, BNB | 15m / 1h / 4h / 1d |
| ZEC                          | 4h                 |

Files are organized as `market_info/{symbol}/{SYMBOL}{interval}_Binance.csv`.

**Download**: [Google Drive](https://drive.google.com/file/d/11J7LR7qp3cVVwsJgQmsWuiw3Tge-QVFV/view)
