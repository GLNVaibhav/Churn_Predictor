from __future__ import annotations
from ..domain.enums import Severity, ValidationOutcome
from ..domain.models import BusinessMeaningResolution, ColumnProfile, ValidationFinding, ValidationResult

class ValidationService:
    def validate(self, column: ColumnProfile, meaning: BusinessMeaningResolution) -> ValidationResult:
        candidate = meaning.selected or (meaning.candidates[0] if meaning.candidates else None)
        if candidate is None: return ValidationResult()
        label = candidate.interpretation.meaning_id.value
        findings = []
        numeric_meaning = any(part in label for part in ("charge", "spend", "count", "tenure", "recency", "score"))
        if numeric_meaning and column.datatype.logical_type not in {"numeric", "boolean"}:
            findings.append(ValidationFinding("datatype.numeric_required", Severity.CRITICAL, ValidationOutcome.CONTRADICTED, "Candidate meaning requires a numeric-compatible source datatype.", (column.raw_column,)))
        elif numeric_meaning:
            findings.append(ValidationFinding("datatype.numeric_supported", Severity.INFO, ValidationOutcome.SUPPORTED, "Numeric source datatype supports candidate meaning.", (column.raw_column,)))
        score = .0 if any(f.severity == Severity.CRITICAL for f in findings) else 1.0
        return ValidationResult(tuple(findings), score)
