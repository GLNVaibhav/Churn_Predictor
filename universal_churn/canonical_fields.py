"""
universal_churn.canonical_fields
==================================
Canonical Field Registry — Phase 1 of "Schema Intelligence
Consolidation" (v5.2).

Before v5.2, the alias/regex mapping used to resolve raw CSV columns
into canonical field names lived as a hard-coded module-level list
directly inside schema_resolution.py (`CANONICAL_FIELDS`). This module
replaces that list with a proper registry:

    CanonicalFieldDefinition  — one canonical field: aliases, regex
                                  patterns, expected dtype, an optional
                                  value parser, which sectors are known
                                  to carry it, and match confidences.
    SectorSchema              — optional per-sector view: which
                                  canonical fields a given sector is
                                  expected to carry (informational,
                                  consumed by reporting/diagnostics —
                                  resolution itself stays sector-agnostic).
    SchemaRegistry            — holds every CanonicalFieldDefinition and
                                  is the ONLY place that knows how to
                                  match a raw column name to a canonical
                                  field. schema_resolution.py now calls
                                  into this registry instead of owning
                                  the mapping itself.

Per architecture rule "Do NOT duplicate schema mappings": this is the
single source of truth. schema_resolution.py, business_concepts.py,
concept_confidence.py, and coverage.py all read canonical field NAMES
that ultimately trace back to definitions registered here — none of
them hard-code an alias list of their own.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable


def _normalize(col: str) -> str:
    """Lowercase, strip, collapse spaces/underscores for exact matching."""
    return col.strip().lower().replace(' ', '').replace('_', '')


# ══════════════════════════════════════════════════════════════════
# DEFINITIONS
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CanonicalFieldDefinition:
    """
    One canonical raw field and everything needed to recognize it in
    an arbitrary, unseen input file.
    """
    name: str
    description: str = ""
    aliases: tuple[str, ...] = ()
    regex_patterns: tuple[str, ...] = ()
    dtype: str = "auto"                       # 'numeric' | 'categorical' | 'datetime' | 'auto'
    parser: Callable[[Any], Any] | None = None  # optional value-coercion hook; not
                                                 # applied by the registry itself —
                                                 # available for callers (e.g. a future
                                                 # concept-first feature_engineering.py)
                                                 # that want typed values, not just names.
    sector_availability: tuple[str, ...] = ()  # sectors known to carry this field;
                                                 # empty tuple = unrestricted/unknown
    alias_confidence: float = 1.0              # confidence for an exact alias hit
    regex_confidence: float = 0.8              # confidence for a regex-pattern hit

    def normalized_aliases(self) -> set[str]:
        return {_normalize(a) for a in self.aliases}

    def compiled_patterns(self) -> list[re.Pattern]:
        return [re.compile(p, re.IGNORECASE) for p in self.regex_patterns]


@dataclass
class SectorSchema:
    """
    Optional, informational per-sector view over the registry: which
    canonical fields a given sector is expected to carry. Currently
    used only for diagnostics/reporting — resolve_schema() matches by
    column name alone and does not consult this.
    """
    sector: str
    expected_fields: tuple[str, ...] = ()


# ══════════════════════════════════════════════════════════════════
# REGISTRY
# ══════════════════════════════════════════════════════════════════

class SchemaRegistry:
    """
    Holds every CanonicalFieldDefinition and is the single matching
    authority: "what canonical field, if any, does this raw column
    name resolve to, and at what confidence?"
    """

    def __init__(self) -> None:
        self._fields: dict[str, CanonicalFieldDefinition] = {}
        self._exact_index: dict[str, str] = {}   # normalized alias -> field name

    def register(self, definition: CanonicalFieldDefinition) -> None:
        if definition.name in self._fields:
            raise ValueError(f"Canonical field '{definition.name}' is already registered.")
        self._fields[definition.name] = definition
        for alias in definition.normalized_aliases():
            # First registration wins on alias collisions rather than silently
            # overwriting — a collision usually means two fields were defined
            # to mean the same raw column, which should be caught in review.
            self._exact_index.setdefault(alias, definition.name)

    def get(self, name: str) -> CanonicalFieldDefinition | None:
        return self._fields.get(name)

    def all(self) -> list[CanonicalFieldDefinition]:
        return list(self._fields.values())

    def names(self) -> list[str]:
        return list(self._fields.keys())

    def match_column(self, raw_column: str) -> tuple[str | None, str, float]:
        """
        Resolve one raw column name.

        Returns
        -------
        (canonical_field_name | None, method, confidence)
            method is one of 'exact' | 'regex' | 'unresolved'.
        """
        normalized = _normalize(raw_column)

        if normalized in self._exact_index:
            field_name = self._exact_index[normalized]
            return field_name, 'exact', self._fields[field_name].alias_confidence

        for definition in self._fields.values():
            for pattern in definition.compiled_patterns():
                if pattern.search(raw_column):
                    return definition.name, 'regex', definition.regex_confidence

        return None, 'unresolved', 0.0


# ══════════════════════════════════════════════════════════════════
# DEFAULT REGISTRATIONS
# ══════════════════════════════════════════════════════════════════
# Migrated verbatim from the pre-v5.2 CANONICAL_FIELDS list that used
# to live in schema_resolution.py — same aliases, same regexes, same
# fields. Only the container changed (list -> registry).

_DEFAULT_FIELD_DEFINITIONS: tuple[CanonicalFieldDefinition, ...] = (
    CanonicalFieldDefinition(
        name="CustomerID_Raw",
        dtype="categorical",
        aliases=(
            "customerID", "CustomerID", "Customer ID", "CustomerId",
            "RowNumber", "PatientID", "patientid",
        ),
        description="Any row-level unique identifier. Never used as a "
                     "model feature — extracted and reattached to results.",
    ),
    CanonicalFieldDefinition(
        name="Recurring_Cost",
        dtype="numeric",
        aliases=(
            "MonthlyCharges", "MonthlyPremium", "SubscriptionFee",
            "Avg_Out_Of_Pocket_Cost", "CashbackAmount",
        ),
        regex_patterns=(r".*charge.*", r".*premium.*", r".*fee.*"),
        sector_availability=("telecom", "healthcare", "ecommerce", "banking"),
        description="Recurring financial commitment — the periodic cost "
                     "the customer pays or the periodic value they "
                     "receive (e.g. cashback). Sector-specific direction "
                     "(cost vs. reward) is resolved in business_concepts.py, "
                     "not here.",
    ),
    CanonicalFieldDefinition(
        name="Total_Spend",
        dtype="numeric",
        aliases=("TotalCharges", "Balance", "Claim Amount"),
        regex_patterns=(r".*total.*charge.*", r".*balance.*"),
        sector_availability=("telecom", "banking"),
        description="Cumulative financial relationship size.",
    ),
    CanonicalFieldDefinition(
        name="Tenure_Raw",
        dtype="numeric",
        aliases=("tenure", "Tenure", "Tenure_Months"),
        regex_patterns=(r".*tenure.*",),
        sector_availability=("telecom", "ecommerce", "banking", "healthcare"),
        description="Length of the customer relationship, in whatever "
                     "unit the source dataset uses (resolved to months "
                     "downstream).",
    ),
    CanonicalFieldDefinition(
        name="Support_Contacts",
        dtype="numeric",
        aliases=(
            "TechSupportCalls", "SupportTickets", "CustomerServiceCalls",
            "CustomerSupportCalls", "Billing_Issues", "Complain",
            "Missed_Appointments",
        ),
        regex_patterns=(r".*support.*", r".*complain.*", r".*billing.*issue.*"),
        sector_availability=("ecommerce", "healthcare", "banking"),
        description="Frequency of customer-initiated support or "
                     "complaint contact, regardless of channel.",
    ),
    CanonicalFieldDefinition(
        name="Satisfaction_Raw",
        dtype="numeric",
        aliases=(
            "SatisfactionScore", "Overall_Satisfaction", "CreditScore",
            "Wait_Time_Satisfaction", "Staff_Satisfaction",
            "Provider_Rating",
        ),
        regex_patterns=(r".*satisfaction.*", r".*rating.*"),
        sector_availability=("ecommerce", "banking", "healthcare"),
        description="A satisfaction-adjacent score. NOTE: CreditScore is "
                     "a financial-health proxy, not a true satisfaction "
                     "measure — this distinction is preserved in "
                     "business_concepts.py via per-sector confidence "
                     "weighting, not silently merged here.",
    ),
    CanonicalFieldDefinition(
        name="Activity_Recency",
        dtype="numeric",
        aliases=(
            "DaySinceLastOrder", "Days_Since_Last_Visit",
            "DaysSinceLastOrder",
        ),
        regex_patterns=(r".*since.*last.*", r".*recency.*"),
        sector_availability=("ecommerce", "healthcare"),
        description="Days since the customer last engaged "
                     "(order / visit / login).",
    ),
    CanonicalFieldDefinition(
        name="Engagement_Volume",
        dtype="numeric",
        aliases=(
            "OrderCount", "Visits_Last_Year", "NumOfProducts",
            "NumberOfDeviceRegistered", "HourSpendOnApp",
        ),
        regex_patterns=(r".*count.*", r".*visits.*", r".*numof.*"),
        sector_availability=("ecommerce", "banking", "healthcare"),
        description="Volume of interaction or product usage — how much "
                     "the customer engages, distinct from how recently.",
    ),
    CanonicalFieldDefinition(
        name="Contract_Commitment",
        dtype="categorical",
        aliases=("Contract", "PolicyType", "Insurance_Type"),
        regex_patterns=(r".*contract.*", r".*policy.*type.*"),
        sector_availability=("telecom", "healthcare"),
        description="The formal commitment structure — contract length "
                     "or policy type — used as a stability signal.",
    ),
    CanonicalFieldDefinition(
        name="Demographic_Risk",
        dtype="numeric",
        aliases=("SeniorCitizen", "Age", "BMI"),
        regex_patterns=(r".*senior.*", r"^age$", r".*bmi.*"),
        sector_availability=("telecom", "banking", "healthcare"),
        description="Demographic attributes used as risk-adjacent "
                     "signals. Thresholds for 'high risk' are sector-"
                     "specific and applied in business_concepts.py.",
    ),
    CanonicalFieldDefinition(
        name="Auto_Payment_Flag",
        dtype="categorical",
        aliases=("PaymentMethod", "PreferredPaymentMode", "HasCrCard"),
        regex_patterns=(r".*payment.*method.*", r".*payment.*mode.*"),
        sector_availability=("telecom", "ecommerce", "banking"),
        description="Whether the customer's payment method implies "
                     "automatic/recurring billing.",
    ),
    CanonicalFieldDefinition(
        name="Active_Status",
        dtype="numeric",
        aliases=("IsActiveMember",),
        regex_patterns=(r".*active.*member.*",),
        sector_availability=("banking",),
        description="Explicit active/inactive flag where the source "
                     "dataset provides one directly.",
    ),
)


def _build_default_registry() -> SchemaRegistry:
    registry = SchemaRegistry()
    for definition in _DEFAULT_FIELD_DEFINITIONS:
        registry.register(definition)
    return registry


# Module-level singleton — the registry instance every other module
# should import and use. Kept mutable (not frozen) so a future
# semantic-matching layer (v5.4 roadmap) or a test can register
# additional fields without touching this file.
CANONICAL_REGISTRY = _build_default_registry()
