import pandas as pd

from fin_features import apply_feature
from indicators import apply_indicator

from .base import Strategy
from .st_vol_band_reversal import STRATEGY as ST_VOL_BAND_REVERSAL
from .st_vrb_clean import STRATEGY as ST_VRB_CLEAN
from .st_vrb_enhanced import STRATEGY as ST_VRB_ENHANCED

STRATEGY_REGISTRY: dict[str, Strategy] = {
    ST_VOL_BAND_REVERSAL.name: ST_VOL_BAND_REVERSAL,
    ST_VRB_CLEAN.name: ST_VRB_CLEAN,
    ST_VRB_ENHANCED.name: ST_VRB_ENHANCED,
}


def get_strategy(name: str) -> Strategy:
    if name not in STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy: {name}. Available strategies: {list(STRATEGY_REGISTRY.keys())}"
        )
    return STRATEGY_REGISTRY[name]


def resolve_params(strategy: Strategy, param_overrides: dict | None = None) -> dict:
    return {**strategy.params, **(param_overrides or {})}


def build_enriched(
    df: pd.DataFrame,
    strategy: Strategy,
    param_overrides: dict | None = None,
) -> pd.DataFrame:
    params = resolve_params(strategy, param_overrides)
    out = df.copy()

    for item in strategy.build_features(params):
        out = apply_feature(out, item["name"], **item.get("params", {}))

    for item in strategy.build_indicators(params):
        out = apply_indicator(out, item["name"], **item.get("params", {}))

    return out


def run_strategy(
    df: pd.DataFrame,
    strategy: Strategy,
    param_overrides: dict | None = None,
) -> pd.DataFrame:
    params = resolve_params(strategy, param_overrides)
    enriched = build_enriched(df, strategy, param_overrides)
    return strategy.generate_signals(enriched, params)
