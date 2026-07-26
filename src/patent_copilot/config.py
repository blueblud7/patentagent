from __future__ import annotations

import os


def clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def get_env_value(name: str) -> str | None:
    return clean_env_value(os.getenv(name))


def env_has_value(name: str) -> bool:
    return get_env_value(name) is not None
