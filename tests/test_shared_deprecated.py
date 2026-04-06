"""Tests for deprecated altapi.shared."""

import importlib
import sys
import warnings


def test_shared_module_emits_deprecation():
    sys.modules.pop("altapi.shared", None)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        importlib.import_module("altapi.shared")
        assert any(issubclass(x.category, DeprecationWarning) for x in w)
