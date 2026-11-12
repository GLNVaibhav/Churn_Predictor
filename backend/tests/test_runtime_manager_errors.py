from backend.runtime.manager import _safe_failure_detail


def test_wrapped_non_csv_failure_is_not_mislabeled_by_csv_filename():
    wrapped = RuntimeError("Framework execution failed for input 'customer.csv'")
    wrapped.__cause__ = ValueError("Unsupported mode 'manual'")

    assert _safe_failure_detail(wrapped) == (
        "Analysis did not complete. Review the dataset and selected sector, then retry."
    )


def test_csv_parser_failure_has_actionable_safe_message():
    wrapped = RuntimeError("Framework execution failed for input 'customer.csv'")
    wrapped.__cause__ = UnicodeDecodeError("utf-8", b"x", 0, 1, "invalid start byte")

    assert _safe_failure_detail(wrapped) == (
        "The uploaded file could not be read as a valid CSV. Check its encoding and delimiter."
    )
