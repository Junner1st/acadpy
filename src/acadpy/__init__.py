"""Draw in a running AutoCAD 2026 using its ActiveX API."""

from .client import AutoCAD, AutoCADConnectionError

__all__ = ["AutoCAD", "AutoCADConnectionError"]
