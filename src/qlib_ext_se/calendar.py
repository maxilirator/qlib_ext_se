from __future__ import annotations

import csv
import os
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Tuple

import pandas as pd
import logging

from .config import get_eodhd_api_key

_CACHE_DIR = os.path.join(os.path.dirname(__file__), "_cache")
_FALLBACK_CSV = os.path.join(
    os.path.dirname(__file__), "data", "xsto_trading_days_fallback.csv"
)


def _ensure_cache_dir() -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _cache_file_name(start: date, end: date) -> str:
    return os.path.join(_CACHE_DIR, f"xsto_{start.isoformat()}_{end.isoformat()}.csv")


def _generate_with_pmc(start: date, end: date) -> pd.DatetimeIndex:
    import pandas_market_calendars as mcal  # heavy dep; import lazily

    xsto = mcal.get_calendar("XSTO")
    sched = xsto.schedule(start_date=start.isoformat(), end_date=end.isoformat())
    idx = pd.DatetimeIndex(sched.index)
    return idx.tz_localize(None)  # session dates as naive timestamps


def _read_days_from_csv(path: str) -> pd.DatetimeIndex:
    df = pd.read_csv(path, parse_dates=["date"])  # columns: date
    return pd.DatetimeIndex(df["date"]).tz_localize(None)


def _business_days_between(start: date, end: date) -> pd.DatetimeIndex:
    # Monday-Friday business days as naive date index
    return pd.bdate_range(start=start, end=end, freq="C").tz_localize(None)


def _fetch_holidays_eodhd(start: date, end: date, api_key: str) -> Optional[set]:
    """Fetch XSTO holidays from EODHD.

    Uses EODHD stock market holidays endpoint. Returns a set of date objects to be excluded.
    If any error occurs, returns None.
    """
    try:
        import requests  # local import to keep optional

        url = (
            "https://eodhd.com/api/exchange-holidays/XSTO"
            f"?from={start.isoformat()}&to={end.isoformat()}&api_token={api_key}&fmt=json"
        )
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        holidays = set()
        # Expected formats vary; handle common shapes
        if isinstance(data, list):
            for item in data:
                # item may be {"date": "YYYY-MM-DD", ...}
                d = item.get("date") if isinstance(item, dict) else None
                if isinstance(d, str) and d:
                    try:
                        holidays.add(datetime.fromisoformat(d).date())
                    except Exception:
                        pass
        elif isinstance(data, dict):
            for k in ("holidays", "data", "items"):
                lst = data.get(k)
                if isinstance(lst, list):
                    for item in lst:
                        d = item.get("date") if isinstance(item, dict) else None
                        if isinstance(d, str) and d:
                            try:
                                holidays.add(datetime.fromisoformat(d).date())
                            except Exception:
                                pass
        return holidays
    except Exception as e:
        logging.getLogger("qlib_ext_se").debug("EODHD holidays fetch failed: %s", e)
        return None


def _generate_with_eodhd(
    start: date, end: date, api_key: str
) -> Optional[pd.DatetimeIndex]:
    """Generate trading days using EODHD holidays by excluding them from business days.

    Returns None if fetch fails.
    """
    holidays = _fetch_holidays_eodhd(start, end, api_key)
    if holidays is None:
        return None
    # Business days Mon-Fri excluding holidays
    bd = _business_days_between(start, end)
    keep = [d for d in bd if d.date() not in holidays]
    return pd.DatetimeIndex(keep).tz_localize(None)


def build_xsto_trading_days(
    start: date, end: date, use_cache: bool = True
) -> pd.DatetimeIndex:
    """Build trading session dates for Stockholm exchange between start and end (inclusive).

    Prefers pandas-market-calendars, caches to a CSV, and falls back to embedded CSV on failure.
    """
    _ensure_cache_dir()
    cache = _cache_file_name(start, end)
    if use_cache and os.path.exists(cache):
        return _read_days_from_csv(cache)

    # 1) Try EODHD if API key present
    api_key = get_eodhd_api_key()
    if api_key:
        idx = _generate_with_eodhd(start, end, api_key)
        if idx is not None and len(idx) > 0:
            logging.getLogger("qlib_ext_se").info(
                "calendar_source=EODHD range=%s..%s count=%d", start, end, len(idx)
            )
            pd.DataFrame({"date": idx.date}).to_csv(cache, index=False)
            return idx

    # 2) Fallback to pandas-market-calendars
    try:
        idx = _generate_with_pmc(start, end)
        logging.getLogger("qlib_ext_se").info(
            "calendar_source=PMC range=%s..%s count=%d", start, end, len(idx)
        )
        pd.DataFrame({"date": idx.date}).to_csv(cache, index=False)
        return idx
    except Exception:
        # 3) Final fallback to embedded CSV
        if os.path.exists(_FALLBACK_CSV):
            idx = _read_days_from_csv(_FALLBACK_CSV)
            mask = (idx.date >= start) & (idx.date <= end)
            logging.getLogger("qlib_ext_se").info(
                "calendar_source=EMBEDDED_CSV range=%s..%s count=%d",
                start,
                end,
                int(mask.sum()),
            )
            return idx[mask]
        raise


def is_trading_day(dt: date) -> bool:
    idx = build_xsto_trading_days(dt, dt)
    return len(idx) > 0 and idx[0].date() == dt


def se_trading_hours() -> Tuple[str, str]:
    """Return standard trading hours for SE in 24h HH:MM:SS local time (CET/CEST)."""
    return ("09:00:00", "17:30:00")
