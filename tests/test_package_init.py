"""Tests for altapi package __init__ lazy exports."""

import warnings

import pytest


def test_getattr_version():
    import altapi

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        v = altapi.__getattr__("__version__")
    assert isinstance(v, str)


def test_getattr_missing_raises():
    import altapi

    with pytest.raises(AttributeError):
        altapi.__getattr__("nonexistent_xyz")


def test_altapi_all_exports_exist():
    import altapi

    for name in altapi.__all__:
        assert hasattr(altapi, name), name


def test_deprecated_import_still_returns_object():
    import altapi

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        req = altapi.Request
        assert w and issubclass(w[0].category, DeprecationWarning)
    assert req is not None
