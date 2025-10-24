from __future__ import annotations

import os
from typing import Optional

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore


def _user_config_dir() -> str:
    # Windows: %APPDATA%\qlib-ext-se, else ~/.config/qlib-ext-se
    appdata = os.getenv("APPDATA")
    if appdata:
        return os.path.join(appdata, "qlib-ext-se")
    return os.path.join(os.path.expanduser("~"), ".config", "qlib-ext-se")


def _config_file_path() -> str:
    return os.path.join(_user_config_dir(), "config.toml")


def _read_toml(path: str) -> dict:
    if not tomllib or not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)  # type: ignore[no-untyped-call]


def get_eodhd_api_key() -> Optional[str]:
    """Return EODHD API key from env or TOML config.

    Priority:
    1) Environment variable EODHD_API_KEY
    2) TOML at <config_dir>/config.toml with key: [eodhd] api_key = "..."
    """
    key = os.getenv("EODHD_API_KEY")
    if key:
        return key
    data = _read_toml(_config_file_path())
    if isinstance(data, dict):
        eod = data.get("eodhd")
        if isinstance(eod, dict):
            k = eod.get("api_key")
            if isinstance(k, str) and k:
                return k
    return None
