from __future__ import annotations

import importlib
from datetime import datetime, time, timedelta
from typing import Any, Callable, Dict

from .compat import ensure_pyqlib_supported
from .defaults import CURRENCY, INDEX, REGION_CODE
from .calendar import se_trading_hours

# Keep original symbols/functions so we can attempt rollback on unregister
_ORIGINALS: Dict[str, Any] = {}


def _monkey_patch_constants() -> None:
    qconst = importlib.import_module("qlib.constant")
    if not hasattr(qconst, "REG_SE"):
        setattr(qconst, "REG_SE", REGION_CODE)


def _patch_default_region_config() -> None:
    qconf = importlib.import_module("qlib.config")
    # qlib.config keeps a _default_region_config dict mapping region code -> dict
    default_map = getattr(qconf, "_default_region_config", None)
    if isinstance(default_map, dict):
        if REGION_CODE not in default_map:
            default_map[REGION_CODE] = {
                "trade_unit": 1,
                "limit_threshold": None,
                "deal_price": "adjusted_close",
            }


def _patch_time_utils() -> None:
    qtime = importlib.import_module("qlib.utils.time")
    qconst = importlib.import_module("qlib.constant")

    # Define SE trading window (no lunch break): 09:00–17:30
    open_s, close_s = se_trading_hours()
    base = datetime(1900, 1, 1)
    SE_TIME = [
        datetime.combine(base.date(), time.fromisoformat(open_s)),
        datetime.combine(base.date(), time.fromisoformat(close_s)),
    ]

    # Preserve originals once
    if "get_min_cal" not in _ORIGINALS:
        _ORIGINALS["get_min_cal"] = getattr(qtime, "get_min_cal")
    if "time_to_day_index" not in _ORIGINALS:
        _ORIGINALS["time_to_day_index"] = getattr(qtime, "time_to_day_index")

    REG_SE = getattr(qconst, "REG_SE", REGION_CODE)

    def get_min_cal_extended(shift: int = 0, region: str = getattr(qconst, "REG_CN")):
        if region == REG_SE:
            cal = []
            for ts in list(
                pd.date_range(
                    SE_TIME[0], SE_TIME[1] - timedelta(minutes=1), freq="1min"
                )
                - pd.Timedelta(minutes=shift)
            ):
                cal.append(ts.time())
            return cal
        return _ORIGINALS["get_min_cal"](shift=shift, region=region)

    def time_to_day_index_extended(time_obj, region: str = getattr(qconst, "REG_CN")):
        if region == REG_SE:
            if isinstance(time_obj, str):
                time_obj = datetime.strptime(time_obj, "%H:%M")
            if SE_TIME[0] <= time_obj < SE_TIME[1]:
                return int((time_obj - SE_TIME[0]).total_seconds() / 60)
            raise ValueError(
                f"{time_obj} is not the opening time of the {region} stock market"
            )
        return _ORIGINALS["time_to_day_index"](time_obj, region=region)

    # Patch module namespace
    import pandas as pd  # local import to avoid hard dependency at import time

    setattr(qtime, "get_min_cal", get_min_cal_extended)
    setattr(qtime, "time_to_day_index", time_to_day_index_extended)


def _structured_info_log() -> None:
    try:
        qlog = importlib.import_module("qlib.log")
        logger = qlog.get_module_logger("qlib_ext_se")
        logger.info(
            "qlib-ext-se: registered region.",
            extra={
                "region": REGION_CODE,
                "calendar": "XSTO",
                "index": INDEX,
                "currency": CURRENCY,
            },
        )
    except Exception:
        pass


def register() -> None:
    """Register the 'se' region into pyqlib 0.9.7.

    Idempotent. Safe no-op if already applied.
    """
    ensure_pyqlib_supported()
    _monkey_patch_constants()
    _patch_default_region_config()
    _patch_time_utils()
    _structured_info_log()


def unregister() -> None:
    """Best-effort rollback of monkey patches introduced by register()."""
    ensure_pyqlib_supported()
    # Remove constant if we created it
    try:
        qconst = importlib.import_module("qlib.constant")
        if getattr(qconst, "REG_SE", None) == REGION_CODE:
            delattr(qconst, "REG_SE")
    except Exception:
        pass

    # Remove default region config entry
    try:
        qconf = importlib.import_module("qlib.config")
        default_map = getattr(qconf, "_default_region_config", None)
        if isinstance(default_map, dict) and REGION_CODE in default_map:
            default_map.pop(REGION_CODE, None)
    except Exception:
        pass

    # Restore original time utils if stored
    try:
        qtime = importlib.import_module("qlib.utils.time")
        if "get_min_cal" in _ORIGINALS:
            setattr(qtime, "get_min_cal", _ORIGINALS["get_min_cal"])
        if "time_to_day_index" in _ORIGINALS:
            setattr(qtime, "time_to_day_index", _ORIGINALS["time_to_day_index"])
    except Exception:
        pass
