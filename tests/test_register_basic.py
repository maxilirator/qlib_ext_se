import importlib

import qlib_ext_se


def test_register_idempotent():
    # First call registers
    qlib_ext_se.register()
    qconst = importlib.import_module("qlib.constant")
    assert getattr(qconst, "REG_SE", None) == "se"

    qconf = importlib.import_module("qlib.config")
    m = getattr(qconf, "_default_region_config", {})
    assert "se" in m
    size_before = len(m)

    # Second call is no-op
    qlib_ext_se.register()
    m2 = getattr(importlib.import_module("qlib.config"), "_default_region_config", {})
    assert len(m2) == size_before


def test_unregister_is_noop_when_unregistered():
    # Ensure we can call unregister twice without error
    qlib_ext_se.unregister()
    qlib_ext_se.unregister()
