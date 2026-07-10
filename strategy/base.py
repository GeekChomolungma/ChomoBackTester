from dataclasses import dataclass, field
from typing import Callable

import pandas as pd


def _no_features(params: dict) -> list[dict]:
    return []


@dataclass
class Strategy:
    """
    A strategy bundles the indicators/features it depends on with the
    logic that turns an enriched OHLCV dataframe into buy/sell signals.

    build_indicators(params) / build_features(params) derive the
    indicators.apply_indicator / fin_features.apply_feature pipeline
    configs from a single flat `params` dict, so a parameter optimizer
    can sweep indicator params and strategy params through the same
    interface without knowing how they're wired internally.

    generate_signals(df, params) must only write a sparse `signal` column:
    most rows are NaN, and only the bar on which a trade actually fills
    carries an event tag (e.g. "long_entry", "short_exit,long_entry").
    """

    name: str
    build_indicators: Callable[[dict], list[dict]]
    generate_signals: Callable[[pd.DataFrame, dict], pd.DataFrame]
    build_features: Callable[[dict], list[dict]] = _no_features
    params: dict = field(default_factory=dict)
