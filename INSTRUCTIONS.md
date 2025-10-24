# Minimal checklist (hand-off)

## Package metadata

- Name/version: qlib-ext-se 0.1.0
- Requires: pyqlib==0.9.7, pandas, pandas-market-calendars, python-dateutil, pytz, requests
- Public API: register(), unregister()

## Region defaults

- code: 'se'
- index: 'OMXS30'
- currency: 'SEK'
- calendar: Preferred EODHD-backed (holidays endpoint) with business day synthesis; fallback to XSTO via pandas-market-calendars; cache CSV

## Registries to update

- config.REG_SE constant in qlib.constant
- qlib.config.\_default_region_config['se']
- qlib.utils.time.get_min_cal / time_to_day_index extended to handle 'se'
- symbol normalization helper provided in this extension

## Tests

- Unit: register/unregister idempotency
- Calendar: Swedish holidays (e.g., 2025-06-20 Midsummer's Eve closed); ensure EODHD path is optional and doesn't break when no key
- Integration: DatasetH smoke with SE_PROVIDER_URI (skipped by default)

## Docker/CI

- Pin versions; run smoke test in container or CI; allow EODHD API key injection via env when testing that path

## Configuration

- EODHD API key lookup order:
  1.  Environment variable `EODHD_API_KEY`
  2.  TOML `%APPDATA%/qlib-ext-se/config.toml` (Windows) or `~/.config/qlib-ext-se/config.toml` with section `[eodhd] api_key = "..."`
