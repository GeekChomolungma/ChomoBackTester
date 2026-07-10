import pandas as pd

TRADE_COLUMNS = [
    "trade_number",
    "side",
    "status",
    "entry_time",
    "entry_price",
    "exit_time",
    "exit_price",
    "pnl",
    "return_pct",
    "bars_held",
]


def extract_trades(
    df: pd.DataFrame,
    price_col: str = "close",
    fill_col: str = "open",
    time_col: str = "datetime",
) -> pd.DataFrame:
    """
    Rebuild a trade list from a sparse `signal` column (see
    strategy.base.Strategy.generate_signals). Each event tag is one of
    long_entry / long_exit / short_entry / short_exit, comma-joined
    when multiple events land on the same bar (e.g. a reversal).

    Entry/exit fills use `fill_col` (default "open") since, by the
    strategy's own no-lookahead convention, the signal is already
    written on the bar it executes on. Any position still open at the
    end of the data is reported with status="open", marked to market
    using the last `price_col` value.
    """
    if "signal" not in df.columns:
        raise ValueError("df must contain a 'signal' column (see strategy.generate_signals)")

    records: list[dict] = []
    open_positions: dict[str, dict] = {}
    trade_counter = 0

    for idx, row in df.iterrows():
        sig = row["signal"]
        if pd.isna(sig):
            continue

        for event in str(sig).split(","):
            side, action = event.split("_")

            if action == "entry":
                trade_counter += 1
                open_positions[side] = {
                    "trade_number": trade_counter,
                    "side": side,
                    "entry_idx": idx,
                    "entry_time": row[time_col],
                    "entry_price": row[fill_col],
                }
            elif action == "exit":
                pos = open_positions.pop(side, None)
                if pos is None:
                    continue

                direction = 1 if side == "long" else -1
                exit_price = row[fill_col]
                pnl = (exit_price - pos["entry_price"]) * direction
                return_pct = pnl / pos["entry_price"] * 100

                records.append(
                    {
                        "trade_number": pos["trade_number"],
                        "side": side,
                        "status": "closed",
                        "entry_time": pos["entry_time"],
                        "entry_price": pos["entry_price"],
                        "exit_time": row[time_col],
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "return_pct": return_pct,
                        "bars_held": idx - pos["entry_idx"],
                    }
                )

    if len(df) > 0 and open_positions:
        last_row = df.iloc[-1]
        for side, pos in open_positions.items():
            direction = 1 if side == "long" else -1
            exit_price = last_row[price_col]
            pnl = (exit_price - pos["entry_price"]) * direction
            return_pct = pnl / pos["entry_price"] * 100

            records.append(
                {
                    "trade_number": pos["trade_number"],
                    "side": side,
                    "status": "open",
                    "entry_time": pos["entry_time"],
                    "entry_price": pos["entry_price"],
                    "exit_time": last_row[time_col],
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "return_pct": return_pct,
                    "bars_held": last_row.name - pos["entry_idx"],
                }
            )

    trades = pd.DataFrame.from_records(records, columns=TRADE_COLUMNS)
    return trades.sort_values("trade_number").reset_index(drop=True)
