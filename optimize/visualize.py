from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from backtest.metrics import EMPTY_METRICS


def plot_heatmap(
    results: pd.DataFrame,
    x_param: str,
    y_param: str,
    metric: str,
    out_path: str | Path,
) -> Path:
    """
    Pivot grid-search results into a (y_param x x_param) heatmap of
    `metric` and save it to out_path. Only meaningful when the grid was
    swept over exactly two varying params (x_param, y_param) -- if more
    params varied, results is first collapsed by taking the best `metric`
    per (x_param, y_param) pair.
    """
    pivot = results.pivot_table(index=y_param, columns=x_param, values=metric, aggfunc="max")

    fig, ax = plt.subplots(figsize=(1.2 * len(pivot.columns) + 2, 1.0 * len(pivot.index) + 2))
    mesh = ax.pcolormesh(pivot.columns, pivot.index, pivot.values, cmap="RdYlGn", shading="nearest")
    fig.colorbar(mesh, ax=ax, label=metric)

    for i, y in enumerate(pivot.index):
        for j, x in enumerate(pivot.columns):
            value = pivot.values[i, j]
            if pd.notna(value):
                ax.text(x, y, f"{value:.2f}", ha="center", va="center", fontsize=8)

    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(f"{metric} heatmap")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    return out_path


def plot_bar_ranking(
    results: pd.DataFrame,
    metric: str,
    out_path: str | Path,
    top_n: int = 15,
    param_cols: list[str] | None = None,
) -> Path:
    """
    Rank all swept param combinations by `metric` and bar-chart the
    top_n. param_cols (default: every column that isn't a known metric
    key) are joined into a single per-bar label, e.g.
    "st_length=10, st_factor=3.0".
    """
    ranked = results.sort_values(metric, ascending=False).head(top_n)

    if param_cols is None:
        param_cols = [c for c in results.columns if c not in EMPTY_METRICS]

    labels = ranked[param_cols].apply(
        lambda row: ", ".join(f"{c}={row[c]}" for c in param_cols), axis=1
    )

    fig, ax = plt.subplots(figsize=(8, 0.4 * len(ranked) + 2))
    ax.barh(labels, ranked[metric])
    ax.invert_yaxis()
    ax.set_xlabel(metric)
    ax.set_title(f"Top {len(ranked)} by {metric}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    return out_path
