"""Helper za preverjanje disabled flag-a v vir YAML datotekah."""

import os
import yaml

_disabled_cache = None


def _load_disabled():
    global _disabled_cache
    if _disabled_cache is not None:
        return _disabled_cache
    disabled = set()
    config_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "sources",
    )
    if os.path.isdir(config_dir):
        for fn in os.listdir(config_dir):
            if not fn.endswith(".yaml"):
                continue
            path = os.path.join(config_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                src = data.get("source", {}) or {}
                if src.get("disabled"):
                    disabled.add(src.get("id"))
            except Exception:
                continue
    _disabled_cache = disabled
    return disabled


def is_source_disabled(source_id: str) -> bool:
    return source_id in _load_disabled()


def reload_disabled_cache():
    global _disabled_cache
    _disabled_cache = None
