from datetime import date

from qlib_ext_se.calendar import build_xsto_trading_days, is_trading_day


def test_midsummer_eve_2025_closed():
    # 2025-06-20 is Midsummer's Eve in Sweden (closed)
    d = date(2025, 6, 20)
    assert is_trading_day(d) is False


def test_random_open_days_around_midsummer_week():
    # Check a few nearby dates using fallback CSV sample
    opens = [
        date(2025, 6, 18),
        date(2025, 6, 19),
        date(2025, 6, 23),
    ]
    for d in opens:
        assert is_trading_day(d) is True
