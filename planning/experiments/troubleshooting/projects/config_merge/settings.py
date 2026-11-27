import json
from pathlib import Path

HERE = Path(__file__).parent


def deep_merge(base, override):
    """Return base with override layered over it; nested dicts merge key by key."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load(config_dir=HERE):
    """Base config.json, with config.local.json (if present) deep-merged over it."""
    config_dir = Path(config_dir)
    cfg = json.loads((config_dir / "config.json").read_text())
    local = config_dir / "config.local.json"
    if local.exists():
        cfg = deep_merge(cfg, json.loads(local.read_text()))
    return cfg
