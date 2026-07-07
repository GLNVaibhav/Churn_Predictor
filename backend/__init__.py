"""
backend
══════════════════════════════════════════════════════════════════════
Backend Integration Layer — Version 8.2, Sprint 1.

IMPORTANT — what this package IS and IS NOT
---------------------------------------------
The backend is NOT the AI framework. It is an adapter layer that
exposes the existing Universal Churn Intelligence Framework
(``universal_churn/``) to future consumers — a REST API, a frontend
application, AI agents, SDKs, and other external integrations.

The framework (``universal_churn/``) remains the single source of
truth for every computation: coverage scoring, concept confidence,
the quality gate, adaptive routing, prediction, prediction
explanation, decision intelligence, and prediction intelligence. This
package computes NOTHING. It only translates already-computed
framework outputs into a stable, versioned public contract
(:class:`backend.contracts.analysis_response.UniversalAnalysisResponse`)
and back.

Dependency direction (never reversed)
----------------------------------------
::

    Frontend / API / SDK / Agent
              |
              v
           backend
              |
              v
        universal_churn  (Universal Churn Intelligence Framework)

``universal_churn/`` must never import anything from ``backend/``.

What this sprint delivers
----------------------------
    1. ``backend.contracts``  — the canonical public response
       contract (``UniversalAnalysisResponse``) and its sections.
    2. ``backend.mappers``    — ``FrameworkMapper``, which converts
       existing framework result objects (dicts or typed dataclasses)
       into the public contract. No business logic, no calculations,
       no validation, no routing, no reasoning — mapping only.
    3. ``backend.exceptions`` — backend-local exception types, kept
       separate from any framework exception.
    4. ``backend.utils``      — small, dependency-free helpers
       (timestamps, ID generation, recursive serialization) shared by
       contracts and mappers.

Explicitly OUT OF SCOPE for this sprint (see the sprint brief):
FastAPI, routers, services, middleware, authentication, a database,
file uploads, background workers, Docker, and frontend integration.
Those are Sprint 2+ concerns and will be built ON TOP of this layer
without changing the public contract defined here.
"""
from __future__ import annotations

BACKEND_VERSION = "0.1.0"

__all__ = ["BACKEND_VERSION"]
