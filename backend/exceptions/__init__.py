"""
backend.exceptions
══════════════════════════════════════════════════════════════════════
Backend-local exception hierarchy.

These are deliberately SEPARATE from any exception the framework
raises (e.g. a refused prediction inside sector_pipeline.py raises a
plain ``ValueError`` today). The backend never re-raises a framework
exception as-is to a future consumer (API, frontend, agent) — it
wraps it in one of these types instead, so a REST layer built on top
of this package (Sprint 2+) can map backend exceptions to HTTP status
codes without inspecting framework internals or coupling to
``universal_churn``'s exception types.
"""
from __future__ import annotations


class BackendError(Exception):
    """Base class for every backend-layer error."""


class MappingError(BackendError):
    """
    Raised by ``backend.mappers.FrameworkMapper`` when a framework
    output cannot be translated into the public contract — e.g. a
    required section is missing entirely, or an unrecognized shape was
    passed. Never raised for a merely *empty* or *None* optional
    section; those map to ``None``/defaults instead (see
    ``framework_mapper.py``'s docstring on graceful degradation).
    """


class ContractValidationError(BackendError):
    """
    Raised when a constructed contract object (e.g.
    ``UniversalAnalysisResponse``) fails a basic structural
    invariant — for example, a required top-level section is missing
    after mapping. This is a backend-contract concern, not a framework
    validation concern (coverage/quality/routing already validate
    their own inputs; this only guards the shape of the OUTPUT
    contract).
    """


class UnsupportedFrameworkOutputError(MappingError):
    """
    Raised when ``FrameworkMapper`` is given an object of a type it
    does not know how to read (neither a recognized dict shape nor an
    attribute-bearing object exposing the expected fields).
    """
