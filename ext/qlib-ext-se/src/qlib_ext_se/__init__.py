"""qlib-ext-se public API.

Provides register() / unregister() for integrating the 'se' region with pyqlib 0.9.7.
"""

from .region import register, unregister

__all__ = ["register", "unregister"]

__version__ = "0.1.0"
