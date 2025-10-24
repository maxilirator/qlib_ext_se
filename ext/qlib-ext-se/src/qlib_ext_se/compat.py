from __future__ import annotations

import importlib
from typing import Tuple


SUPPORTED_PYQLIB_VERSIONS: Tuple[str, ...] = ("0.9.7",)


def ensure_pyqlib_supported() -> None:
    """Fail fast if pyqlib is missing or version is unsupported.

    Raises RuntimeError with actionable guidance.
    """
    try:
        qlib = importlib.import_module("qlib")
    except Exception as e:  # pragma: no cover - environment issue
        raise RuntimeError(
            "pyqlib is not installed. Please install pyqlib==0.9.7 before using qlib-ext-se."
        ) from e

    ver = getattr(qlib, "__version__", None)
    if ver not in SUPPORTED_PYQLIB_VERSIONS:
        raise RuntimeError(
            f"qlib-ext-se supports pyqlib versions {SUPPORTED_PYQLIB_VERSIONS}, found {ver}. "
            "Pin pyqlib==0.9.7 or see the extension README for guidance."
        )
