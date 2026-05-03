from .returns import add_log_return


FEATURE_REGISTRY = {
    "log_return": add_log_return,
}


def apply_feature(df, name: str, **params):
    if name not in FEATURE_REGISTRY:
        raise ValueError(
            f"Unknown feature: {name}. "
            f"Available features: {list(FEATURE_REGISTRY.keys())}"
        )

    return FEATURE_REGISTRY[name](df, **params)