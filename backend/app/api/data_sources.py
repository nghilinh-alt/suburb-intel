"""Deprecated: AustralianDataSources has moved into the data_sources package.

This file is shadowed by the `data_sources/` package and is kept only because
the workspace filesystem disallows deletion. New code should import from
``app.api.data_sources`` (the package), e.g.::

    from app.api.data_sources import AustralianDataSources

The class implementation now lives in ``app/api/data_sources/abs.py``.
"""

from app.api.data_sources.abs import AustralianDataSources  # noqa: F401

__all__ = ["AustralianDataSources"]
