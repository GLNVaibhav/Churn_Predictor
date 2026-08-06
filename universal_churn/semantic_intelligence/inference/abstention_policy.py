from __future__ import annotations
from ..domain.enums import AbstentionStatus
from ..domain.models import AbstentionDecision, CalibratedConfidence, ValidationResult
class AbstentionPolicy:
    def decide(self, confidence: CalibratedConfidence, validation: ValidationResult, deterministic: bool = False) -> AbstentionDecision:
        if deterministic: return AbstentionDecision(AbstentionStatus.ACCEPTED, "Deterministic precedence locks the resolution.")
        if validation.blocking: return AbstentionDecision(AbstentionStatus.ABSTAINED, "Critical validation contradiction blocks semantic acceptance.")
        if confidence.probability >= .55 and confidence.margin >= .05: return AbstentionDecision(AbstentionStatus.ACCEPTED, "Calibrated confidence and separation meet acceptance policy.")
        if confidence.probability >= .35: return AbstentionDecision(AbstentionStatus.REVIEW_REQUIRED, "Candidate evidence is plausible but below automatic acceptance threshold.")
        return AbstentionDecision(AbstentionStatus.ABSTAINED, "Insufficient calibrated confidence.")
