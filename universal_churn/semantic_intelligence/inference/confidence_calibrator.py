from __future__ import annotations
from ..domain.models import CalibratedConfidence
class ConfidenceCalibrator:
    def calibrate(self, score: float, second_score: float = 0.0) -> CalibratedConfidence:
        # Calibration intentionally preserves a strict semantic ceiling below
        # regex confidence while not suppressing independently corroborated
        # evidence below the automatic-acceptance threshold.
        probability = max(0.0, min(.79, score * .95))
        margin = max(0.0, score - second_score)
        return CalibratedConfidence(score, probability, 1.0 - probability, margin, "high" if probability >= .65 else "medium" if probability >= .45 else "low")
