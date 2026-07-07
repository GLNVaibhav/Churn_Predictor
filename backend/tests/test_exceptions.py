"""Tests for backend.exceptions hierarchy."""
from __future__ import annotations

from backend.exceptions import (
    BackendError, MappingError, ContractValidationError,
    UnsupportedFrameworkOutputError,
)


def test_mapping_error_is_backend_error():
    assert issubclass(MappingError, BackendError)


def test_unsupported_framework_output_is_mapping_error():
    assert issubclass(UnsupportedFrameworkOutputError, MappingError)
    assert issubclass(UnsupportedFrameworkOutputError, BackendError)


def test_contract_validation_error_is_backend_error():
    assert issubclass(ContractValidationError, BackendError)


def test_exceptions_carry_messages():
    try:
        raise UnsupportedFrameworkOutputError("bad shape")
    except BackendError as exc:
        assert "bad shape" in str(exc)
