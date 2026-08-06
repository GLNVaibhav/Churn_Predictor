from __future__ import annotations
import pandas as pd
from ..domain.enums import ResolutionStatus
from ..domain.models import ResolvedSchema

class LegacySchemaAdapter:
    """Projects authoritative V8 resolutions into the immutable legacy contract."""
    def project(self, df: pd.DataFrame, resolved_schema: ResolvedSchema):
        from universal_churn.schema_resolution import ColumnResolution
        rename_map, projected = {}, []
        for resolution in resolved_schema.resolutions:
            if resolution.status in {ResolutionStatus.DETERMINISTIC_EXACT, ResolutionStatus.DETERMINISTIC_REGEX}:
                field, method, score = resolution.deterministic_canonical_field, resolution.deterministic_method, resolution.confidence.probability
            elif resolution.status == ResolutionStatus.SEMANTIC_ACCEPTED and resolution.assignment.canonical_id:
                field, method, score = self._legacy_name(resolution.assignment.canonical_id.value), "semantic", resolution.confidence.probability
            else: field, method, score = None, "unresolved", 0.0
            if field: rename_map[resolution.raw_column] = field
            projected.append(ColumnResolution(resolution.raw_column, field, method, score, resolution.confidence.raw_score if method == "semantic" else None, resolution.abstention.rationale if method == "semantic" else None))
        return df.rename(columns=rename_map), projected
    @staticmethod
    def _legacy_name(canonical_id: str) -> str:
        mapping = {"ucif.canonical.customer.identifier": "CustomerID_Raw", "ucif.canonical.customer.relationship.tenure": "Tenure_Raw", "ucif.canonical.financial.recurring_charge": "Recurring_Cost", "ucif.canonical.financial.total_spend": "Total_Spend", "ucif.canonical.support.interaction_count": "Support_Contacts", "ucif.canonical.customer.activity_recency": "Activity_Recency", "ucif.canonical.customer.satisfaction_score": "Satisfaction_Raw", "ucif.canonical.risk.churn": "Churn_Target"}
        return mapping.get(canonical_id, canonical_id.rsplit(".", 1)[-1])
