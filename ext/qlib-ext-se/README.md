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

## Using from a child app (e.g., qlib_trading)

1) Install dependencies (in your app’s environment):

    - Either install from this repo (editable):

            pip install -e ./ext/qlib-ext-se

    - Or publish and install from your artifact registry as `qlib-ext-se`.

2) Configure EODHD (optional but recommended for high-quality calendar):

    - Environment: `EODHD_API_KEY="<your key>"`
    - Or TOML:

            # Windows
            %APPDATA%/qlib-ext-se/config.toml

            # Linux/macOS
            ~/.config/qlib-ext-se/config.toml

            [eodhd]
            api_key = "YOUR_KEY"

3) Use at startup before qlib.init:

     import qlib_ext_se
     qlib_ext_se.register()  # idempotent

     import qlib
     qlib.init(provider_uri=..., region='se', logging_config=None)

4) Proceed as usual with DatasetH/Trainer; the extension supplies:

    - Region code: `se`
    - Default index: `OMXS30`
    - Currency: `SEK`
    - Trading hours (minute utils): 09:00–17:30 CET/CEST
    - Default deal_price: `adjusted_close`

Note on Docker: You can omit the extension’s Dockerfile and instead build a single trainer image that includes all custom packages (install this extension in that image). The extension does not require its own container.
