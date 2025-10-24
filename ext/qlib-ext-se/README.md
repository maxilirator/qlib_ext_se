# qlib-ext-se

Sweden (SE) region extension for pyqlib 0.9.7. Adds a clean runtime registration for region='se', a Stockholm (XSTO) calendar, sensible defaults, and utilities.

- Public API: register(), unregister()
- Region defaults: code=se, index=OMXS30, currency=SEK, trading hours 09:00–17:30 CET/CEST
- pyqlib support: version-guarded for pyqlib==0.9.7

## Quick start

    import qlib_ext_se
    qlib_ext_se.register()  # idempotent

    import qlib
    qlib.init(provider_uri=..., region='se')

If you don’t have a Swedish provider_uri yet, you can still register to enable config and time utilities; daily calendars come from your data provider.

## Calendar

- Preferred: EODHD holidays + business days when EODHD API key is configured. Set it via:

  - Environment: `EODHD_API_KEY="<your key>"`
  - Or TOML: `%APPDATA%/qlib-ext-se/config.toml` (Windows) or `~/.config/qlib-ext-se/config.toml` with:

              [eodhd]
              api_key = "YOUR_KEY"

- If no API key is present or request fails, falls back to `pandas-market-calendars` XSTO and caches sessions to CSV.
- As a last resort, falls back to an embedded CSV snapshot of trading days for a small audited window.

## Tests

- Unit tests cover registration idempotency and calendar holiday checks.
- Integration test for DatasetH is skipped unless SE_PROVIDER_URI is provided.

## Unregister

    qlib_ext_se.unregister()  # best-effort rollback of monkey patches

## License

MIT
