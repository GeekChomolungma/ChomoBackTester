import numpy as np
import pandas as pd

EMPTY_METRICS = {
    "total_trades": 0,
    "open_trades": 0,
    "winners": 0,
    "losers": 0,
    "win_rate": np.nan,
    "net_pnl": 0.0,
    "gross_profit": 0.0,
    "gross_loss": 0.0,
    "profit_factor": np.nan,
    "avg_pnl": np.nan,
    "avg_win": np.nan,
    "avg_loss": np.nan,
    "avg_win_loss_ratio": np.nan,
    "largest_win": np.nan,
    "largest_loss": np.nan,
    "max_drawdown": 0.0,
    "sharpe_ratio": np.nan,
    "sortino_ratio": np.nan,
    "max_consecutive_wins": 0,
    "max_consecutive_losses": 0,
}


def compute_metrics(trades: pd.DataFrame) -> dict:
    """
    Core backtest metrics computed from the trade list produced by
    backtest.trades.extract_trades(). Only status=="closed" trades feed
    the metrics; open trades are reported separately via "open_trades".

    Sharpe/Sortino are computed on the per-trade return_pct series (not
    a periodic equity curve) and are NOT annualized -- bar frequency
    varies by symbol/interval, so any annualization factor would be a
    guess. Treat them as a relative ranking signal across parameter
    combinations, not a like-for-like number against platforms that
    mark-to-market on a fixed daily/annual basis.

    Max drawdown is computed on the closed-trade cumulative PnL curve
    (close-to-close equivalent), not intrabar equity.
    """
    if trades is None or len(trades) == 0:
        return dict(EMPTY_METRICS)

    closed = trades[trades["status"] == "closed"]
    open_trades = trades[trades["status"] == "open"]

    total_trades = len(closed)
    if total_trades == 0:
        metrics = dict(EMPTY_METRICS)
        metrics["open_trades"] = len(open_trades)
        return metrics

    pnl = closed["pnl"]
    returns = closed["return_pct"]

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    gross_profit = wins.sum()
    gross_loss = -losses.sum()
    net_pnl = pnl.sum()

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan

    cumulative = pnl.cumsum()
    running_max = cumulative.cummax()
    max_drawdown = (running_max - cumulative).max()

    ret_std = returns.std(ddof=1)
    sharpe_ratio = returns.mean() / ret_std if ret_std and not np.isnan(ret_std) else np.nan

    downside_std = returns[returns < 0].std(ddof=1)
    sortino_ratio = (
        returns.mean() / downside_std
        if downside_std and not np.isnan(downside_std)
        else np.nan
    )

    is_win = (pnl > 0).to_numpy()

    return {
        "total_trades": total_trades,
        "open_trades": len(open_trades),
        "winners": len(wins),
        "losers": len(losses),
        "win_rate": len(wins) / total_trades * 100,
        "net_pnl": net_pnl,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "avg_pnl": pnl.mean(),
        "avg_win": wins.mean() if len(wins) else np.nan,
        "avg_loss": losses.mean() if len(losses) else np.nan,
        "avg_win_loss_ratio": (wins.mean() / -losses.mean()) if len(wins) and len(losses) else np.nan,
        "largest_win": pnl.max(),
        "largest_loss": pnl.min(),
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "max_consecutive_wins": _max_consecutive_run(is_win, True),
        "max_consecutive_losses": _max_consecutive_run(is_win, False),
    }


def _max_consecutive_run(is_win: np.ndarray, target: bool) -> int:
    best = 0
    current = 0
    for value in is_win:
        if value == target:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best
