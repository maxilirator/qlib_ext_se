from __future__ import annotations

REGION_CODE = "se"
INDEX = "OMXS30"
CURRENCY = "SEK"


def normalize_symbol(symbol: str) -> str:
    """Normalization heuristic for Swedish tickers.

    Keeps uppercase and strips common suffixes like .ST if present, then re-adds standardized .ST.
    """
    if not symbol:
        return symbol
    s = symbol.strip().upper()
    if s.endswith(".ST"):
        s = s[:-3]
    # Basic cleanup of spaces/hyphens
    s = s.replace(" ", "").replace("-", "")
    return f"{s}.ST"
