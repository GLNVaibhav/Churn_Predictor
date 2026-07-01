"""
universal_churn.business_concepts
===================================
Business Concept Registry — Phase 2 of "Schema Intelligence
Consolidation" (v5.2).

Canonical Raw Fields -> Business Concepts

This is the successor to concepts.py (kept in place as a thin
backward-compatibility shim — see the bottom of this module's sibling
file, concepts.py). The structure is unchanged in spirit (a
sector-independent idea like "how loyal is this customer", built from
one canonical field per sector at a documented confidence), but each
concept is now expressed as a BusinessConceptDefinition that declares:

    required_canonical_fields  — canonical fields (canonical_fields.py)
                                  this concept can be reconstructed
                                  from at near-direct confidence
                                  (>= 0.9) for at least one sector.
    optional_canonical_fields  — canonical fields this concept can
                                  fall back to at lower (proxy)
                                  confidence.
    reconstruction_strategy    — short label for HOW the concept value
                                  is computed from its source field
                                  ('direct', 'proxy_substitution',
                                  'inverted_proxy', 'thresholded').
    weight                     — business importance, 1 (minor) to 5
                                  (critical). Consumed by
                                  concept_confidence.py's weighted
                                  Overall Concept Confidence (Phase 3).
    documentation               — human-readable definition (renamed
                                  from `definition` for parity with the
                                  architecture spec's field name).

required_canonical_fields / optional_canonical_fields are DERIVED from
each concept's per-sector `sources` dict (still the actual source of
truth for "which raw field, at what confidence, with what transform,
for which sector") rather than hand-duplicated — per architecture
rule "Do NOT duplicate schema mappings", nothing here re-lists an
alias or a canonical field name that canonical_fields.py doesn't
already own.

Concept Registry (this build: 5 concepts) — unchanged from the
pre-v5.2 build:
    RECURRING_COMMITMENT  — periodic financial relationship size
    CUSTOMER_LOYALTY      — length/depth of the relationship over time
    SUPPORT_FRICTION      — how much the customer has had to complain/ask for help
    ENGAGEMENT_LEVEL      — how actively the customer uses the product/service
    SATISFACTION_SIGNAL   — any available satisfaction-adjacent score
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# ══════════════════════════════════════════════════════════════════
# CONCEPT DEFINITIONS
# ══════════════════════════════════════════════════════════════════

# A source is still confidence >= 0.9 = "near-direct" for the purposes
# of the required/optional split below.
_NEAR_DIRECT_THRESHOLD = 0.9


@dataclass
class ConceptSource:
    """One sector's contribution to a concept."""
    canonical_field: str
    confidence: float            # 1.0 = direct measure, <1.0 = proxy
    note: str = ""                # why confidence is <1.0, if applicable
    transform: str = "identity"   # 'identity' | 'invert' | 'threshold'
    threshold_value: float | None = None  # used when transform='threshold'

    @property
    def reconstruction_strategy(self) -> str:
        if self.transform == "invert":
            return "inverted_proxy" if self.confidence < 1.0 else "inverted_direct"
        if self.transform == "threshold":
            return "thresholded"
        return "direct" if self.confidence >= _NEAR_DIRECT_THRESHOLD else "proxy_substitution"


@dataclass
class BusinessConceptDefinition:
    name: str
    documentation: str
    value_range: tuple[float, float] = (0.0, 1.0)
    weight: int = 3                                    # 1 (minor) .. 5 (critical)
    sources: dict[str, ConceptSource] = field(default_factory=dict)

    def confidence_for(self, sector: str) -> float:
        src = self.sources.get(sector)
        return src.confidence if src else 0.0

    def is_available_for(self, sector: str) -> bool:
        return sector in self.sources

    @property
    def required_canonical_fields(self) -> tuple[str, ...]:
        """Canonical fields that reconstruct this concept near-directly
        (confidence >= 0.9) for at least one sector."""
        return tuple(sorted({
            s.canonical_field for s in self.sources.values()
            if s.confidence >= _NEAR_DIRECT_THRESHOLD
        }))

    @property
    def optional_canonical_fields(self) -> tuple[str, ...]:
        """Canonical fields that only reconstruct this concept as a
        weaker documented proxy (confidence < 0.9)."""
        return tuple(sorted({
            s.canonical_field for s in self.sources.values()
            if s.confidence < _NEAR_DIRECT_THRESHOLD
        }))

    @property
    def reconstruction_strategies(self) -> dict[str, str]:
        """sector -> reconstruction_strategy label, for diagnostics."""
        return {sector: src.reconstruction_strategy for sector, src in self.sources.items()}

    # Backward-compat alias — pre-v5.2 code referred to this as `definition`.
    @property
    def definition(self) -> str:
        return self.documentation


BUSINESS_CONCEPTS: dict[str, BusinessConceptDefinition] = {

    "RECURRING_COMMITMENT": BusinessConceptDefinition(
        name="RECURRING_COMMITMENT",
        weight=5,
        documentation=(
            "The size of the customer's periodic financial relationship "
            "with the business — what they pay (cost) or what they "
            "receive (reward) on a recurring basis."
        ),
        value_range=(0.0, 1.0),
        sources={
            "telecom": ConceptSource(
                canonical_field="Recurring_Cost", confidence=1.0,
                note="Direct measure — MonthlyCharges.",
            ),
            "healthcare": ConceptSource(
                canonical_field="Recurring_Cost", confidence=1.0,
                note="Direct measure — Avg_Out_Of_Pocket_Cost / "
                     "premium-equivalent.",
            ),
            "ecommerce": ConceptSource(
                canonical_field="Recurring_Cost", confidence=0.7,
                note="Proxy — CashbackAmount is a reward, not a cost. "
                     "Inverted relationship to the other sectors; "
                     "transform='invert' compensates for sign only, "
                     "not for the underlying construct difference.",
                transform="invert",
            ),
            "banking": ConceptSource(
                canonical_field="Total_Spend", confidence=0.6,
                note="Proxy — Balance is an asset stock, not a "
                     "recurring payment flow. Weakest mapping in this "
                     "concept; documented explicitly rather than "
                     "silently averaged in.",
            ),
        },
    ),

    "CUSTOMER_LOYALTY": BusinessConceptDefinition(
        name="CUSTOMER_LOYALTY",
        weight=4,
        documentation=(
            "How long and how committed the customer relationship is — "
            "combines raw tenure with any formal commitment structure "
            "(contract length / policy type) where available."
        ),
        value_range=(0.0, 1.0),
        sources={
            "telecom": ConceptSource(
                canonical_field="Tenure_Raw", confidence=1.0,
                note="Direct measure — tenure in months.",
            ),
            "ecommerce": ConceptSource(
                canonical_field="Tenure_Raw", confidence=1.0,
                note="Direct measure — Tenure in months.",
            ),
            "banking": ConceptSource(
                canonical_field="Tenure_Raw", confidence=1.0,
                note="Direct measure — Tenure in years (normalised "
                     "the same as months elsewhere; absolute units "
                     "differ but the [0,1] normalisation makes this "
                     "comparable across sectors).",
            ),
            "healthcare": ConceptSource(
                canonical_field="Tenure_Raw", confidence=1.0,
                note="Direct measure — Tenure_Months.",
            ),
        },
    ),

    "SUPPORT_FRICTION": BusinessConceptDefinition(
        name="SUPPORT_FRICTION",
        weight=4,
        documentation=(
            "How much the customer has had to engage with support, "
            "complaints, or billing-issue channels. Higher friction is "
            "a churn risk signal across every sector observed so far."
        ),
        value_range=(0.0, 1.0),
        sources={
            "ecommerce": ConceptSource(
                canonical_field="Support_Contacts", confidence=1.0,
                note="Direct measure — Complain flag.",
            ),
            "healthcare": ConceptSource(
                canonical_field="Support_Contacts", confidence=0.9,
                note="Near-direct — Billing_Issues count is a strong "
                     "but not perfect proxy for support friction "
                     "(does not capture clinical complaints).",
            ),
            "banking": ConceptSource(
                canonical_field="Support_Contacts", confidence=0.7,
                note="Proxy — CustomerSupportCalls if present in a "
                     "given export; not present in the baseline "
                     "Churn_Modelling.csv schema, so this concept is "
                     "often unavailable for Banking (confidence "
                     "reflects reliability when the column IS present).",
            ),
            # telecom intentionally has no SUPPORT_FRICTION source in
            # the baseline schema (TechSupport is a service flag, not
            # a complaint count) — left undefined rather than forcing
            # a low-confidence guess. is_available_for('telecom')
            # returns False, which coverage.py treats as "no signal",
            # not "bad signal".
        },
    ),

    "ENGAGEMENT_LEVEL": BusinessConceptDefinition(
        name="ENGAGEMENT_LEVEL",
        weight=3,
        documentation=(
            "How actively the customer uses the product or service — "
            "volume of interaction combined with recency of last "
            "interaction where both are available."
        ),
        value_range=(0.0, 1.0),
        sources={
            "ecommerce": ConceptSource(
                canonical_field="Engagement_Volume", confidence=1.0,
                note="Direct measure — OrderCount, recency from "
                     "Activity_Recency combined in feature_engineering.",
            ),
            "telecom": ConceptSource(
                canonical_field="Engagement_Volume", confidence=0.8,
                note="Proxy — number of services subscribed to "
                     "(PhoneService, StreamingTV, etc.) is a usage-"
                     "breadth signal, not a usage-frequency signal.",
            ),
            "banking": ConceptSource(
                canonical_field="Engagement_Volume", confidence=0.9,
                note="Near-direct — NumOfProducts combined with "
                     "IsActiveMember.",
            ),
            "healthcare": ConceptSource(
                canonical_field="Engagement_Volume", confidence=0.9,
                note="Near-direct — Visits_Last_Year combined with "
                     "Activity_Recency (Days_Since_Last_Visit).",
            ),
        },
    ),

    "SATISFACTION_SIGNAL": BusinessConceptDefinition(
        name="SATISFACTION_SIGNAL",
        weight=4,
        documentation=(
            "Any available satisfaction-adjacent score. EXPLICITLY "
            "NOT assumed equivalent across sectors — confidence below "
            "1.0 means the source is a proxy, and callers should treat "
            "the resulting feature directionally rather than as a "
            "precise satisfaction measurement."
        ),
        value_range=(0.0, 1.0),
        sources={
            "ecommerce": ConceptSource(
                canonical_field="Satisfaction_Raw", confidence=1.0,
                note="Direct measure — explicit 1-5 SatisfactionScore "
                     "survey field.",
            ),
            "healthcare": ConceptSource(
                canonical_field="Satisfaction_Raw", confidence=1.0,
                note="Direct measure — Overall_Satisfaction survey "
                     "field.",
            ),
            "banking": ConceptSource(
                canonical_field="Satisfaction_Raw", confidence=0.4,
                note="WEAK PROXY — CreditScore measures financial "
                     "health, not customer satisfaction. Retained with "
                     "low confidence (rather than excluded) so the "
                     "concept layer still produces a value for Banking, "
                     "but the 0.4 confidence is the explicit, "
                     "documented flag that this is NOT a true "
                     "satisfaction measure. This directly addresses "
                     "the construct-validity issue raised in the "
                     "architecture review.",
            ),
            # telecom has no satisfaction-adjacent column in the
            # baseline schema at all — left undefined.
        },
    ),
}


CONCEPT_NAMES = list(BUSINESS_CONCEPTS.keys())
CONCEPT_WEIGHTS: dict[str, int] = {name: c.weight for name, c in BUSINESS_CONCEPTS.items()}


# ══════════════════════════════════════════════════════════════════
# TRANSFORM HELPERS
# ══════════════════════════════════════════════════════════════════

def _safe_normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize a numeric series into [0, 1]. Constant or
    all-null series normalize to 0.5 (neutral) rather than NaN/inf."""
    s = pd.to_numeric(series, errors='coerce')
    if s.isna().all():
        return pd.Series(0.5, index=series.index)
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series(0.5, index=series.index)
    return ((s - lo) / (hi - lo)).fillna(0.5)


def _apply_transform(series: pd.Series, source: ConceptSource) -> pd.Series:
    normalized = _safe_normalize(series)
    if source.transform == "invert":
        return 1.0 - normalized
    if source.transform == "threshold" and source.threshold_value is not None:
        raw = pd.to_numeric(series, errors='coerce')
        return (raw > source.threshold_value).astype(float)
    return normalized


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════

def compute_concept_values(
    canonical_df: pd.DataFrame,
    sector: str,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """
    Compute the 5 business-concept columns for every row, given a
    DataFrame whose columns have already been resolved to canonical
    field names by schema_resolution.resolve_schema().

    Returns
    -------
    concept_df : pd.DataFrame
        One column per concept in CONCEPT_NAMES, each in [0, 1].
        Concepts with no source for this sector are filled with 0.5
        (neutral) and flagged as unavailable in concept_confidence.

    concept_confidence : dict[str, float]
        concept_name -> confidence (0.0 if unavailable for this
        sector, otherwise the documented source confidence). This is
        a per-row-table companion to (and computed independently of)
        concept_confidence.py's file-level Concept Confidence Engine.
    """
    concept_df = pd.DataFrame(index=canonical_df.index)
    concept_confidence: dict[str, float] = {}

    for concept_name, concept in BUSINESS_CONCEPTS.items():
        source = concept.sources.get(sector)

        if source is None:
            # No documented mapping for this sector — neutral value,
            # zero confidence. Coverage engine treats this as "missing
            # concept", not "bad concept".
            concept_df[concept_name] = 0.5
            concept_confidence[concept_name] = 0.0
            continue

        if source.canonical_field not in canonical_df.columns:
            # Concept IS documented for this sector but the expected
            # canonical field didn't actually resolve from this
            # particular input file — also zero confidence.
            concept_df[concept_name] = 0.5
            concept_confidence[concept_name] = 0.0
            continue

        raw_series = canonical_df[source.canonical_field]
        concept_df[concept_name] = _apply_transform(raw_series, source)
        concept_confidence[concept_name] = source.confidence

    return concept_df, concept_confidence


def describe_concepts_for_sector(sector: str) -> list[dict]:
    """
    Human-readable summary of how each concept resolves for a given
    sector. Used by the CLI report and by documentation generation —
    this is what makes the concept layer auditable rather than a
    black box.
    """
    rows = []
    for concept_name, concept in BUSINESS_CONCEPTS.items():
        source = concept.sources.get(sector)
        rows.append({
            'concept'                : concept_name,
            'documentation'          : concept.documentation,
            'weight'                 : concept.weight,
            'available'              : source is not None,
            'canonical_field'        : source.canonical_field if source else None,
            'confidence'             : source.confidence if source else 0.0,
            'reconstruction_strategy': source.reconstruction_strategy if source else None,
            'note'                   : source.note if source else "Not defined for this sector.",
        })
    return rows
