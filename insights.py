"""Compatibility import; implementation lives in backend_modules.dashboard.insights."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module("backend_modules.dashboard.insights")
