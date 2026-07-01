"""
universal_churn.schema_resolution
==================================
Schema Resolution Layer — Step 1 of the schema-adaptive pipeline.

Unknown CSV columns -> Canonical Raw Fields

This module replaces the old flat GLOBAL_CONCEPT_MAP lookup with a
two-strategy resolver that tracks *how* each column was matched and
*how confident* that match is. The confidence score becomes an input
to the Coverage & Information Quality Engine downstream — a fuzzy or
regex match should count less toward coverage than an exact alias hit.

Strategy order (first hit wins, in this priority):
    1. Exact match   (confidence 1.0)  — column name == known alias
    2. Regex match    (confidence 0.8)  — column name matches a pattern
    Fuzzy matching is intentionally NOT implemented yet — see the
    module docstring note at the bottom for why, and how to add it
    later without touching any other module.

Canonical Raw Fields
---------------------
A canonical field is the standardized name used everywhere downstream
(feature engineering, business concepts, scaling). Examples:

    'Recurring_Cost'   <- MonthlyCharges, MonthlyPremium, SubscriptionFee
    'Support_Contacts' <- TechSupportCalls, SupportTickets, Billing_Issues
    'Tenure_Raw'       <- tenure, Tenure, Tenure_Months
    'Satisfaction_Raw' <- SatisfactionScore, Overall_Satisfaction, CreditScore

This is intentionally a *thin* layer — it only renames columns. It does
NOT compute anything or change values. That happens one layer up, in
concepts.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd


# ══════════════════════════════════════════════════════════════════
# CANONICAL FIELD REGISTRY
# ══════════════════════════════════════════════════════════════════
# Each canonical field lists:
#   exact_aliases : column names matched verbatim (case/space/underscore
#                   insensitive) -> confidence 1.0
#   regex_patterns: compiled patterns tried if no exact alias matched
#                   -> confidence 0.8
#
# To register a new alias for an existing canonical field, add one
# string to its exact_aliases list. Nothing else needs to change —
# this is the single registration point referenced in the package
# docstring.

@dataclass
class CanonicalField:
    name: str
    exact_aliases: list[str] = field(default_factory=list)
    regex_patterns: list[str] = field(default_factory=list)
    description: str = ""

    def _normalized_aliases(self) -> set[str]:
        return {_normalize(a) for a in self.exact_aliases}

    def _compiled_patterns(self) -> list[re.Pattern]:
        return [re.compile(p, re.IGNORECASE) for p in self.regex_patterns]


def _normalize(col: str) -> str:
    """Lowercase, strip, collapse spaces/underscores for exact matching."""
    return col.strip().lower().replace(' ', '').replace('_', '')


CANONICAL_FIELDS: list[CanonicalField] = [
    CanonicalField(
        name="CustomerID_Raw",
        exact_aliases=[
            "customerID", "CustomerID", "Customer ID", "CustomerId",
            "RowNumber", "PatientID", "patientid",
        ],
        description="Any row-level unique identifier. Never used as a "
                     "model feature — extracted and reattached to results.",
    ),
    CanonicalField(
        name="Recurring_Cost",
        exact_aliases=[
            "MonthlyCharges", "MonthlyPremium", "SubscriptionFee",
            "Avg_Out_Of_Pocket_Cost", "CashbackAmount",
        ],
        regex_patterns=[r".*charge.*", r".*premium.*", r".*fee.*"],
        description="Recurring financial commitment — the periodic cost "
                     "the customer pays or the periodic value they "
                     "receive (e.g. cashback). Sector-specific direction "
                     "(cost vs. reward) is resolved in concepts.py, not "
                     "here.",
    ),
    CanonicalField(
        name="Total_Spend",
        exact_aliases=["TotalCharges", "Balance", "Claim Amount"],
        regex_patterns=[r".*total.*charge.*", r".*balance.*"],
        description="Cumulative financial relationship size.",
    ),
    CanonicalField(
        name="Tenure_Raw",
        exact_aliases=["tenure", "Tenure", "Tenure_Months"],
        regex_patterns=[r".*tenure.*"],
        description="Length of the customer relationship, in whatever "
                     "unit the source dataset uses (resolved to months "
                     "downstream).",
    ),
    CanonicalField(
        name="Support_Contacts",
        exact_aliases=[
            "TechSupportCalls", "SupportTickets", "CustomerServiceCalls",
            "CustomerSupportCalls", "Billing_Issues", "Complain",
            "Missed_Appointments",
        ],
        regex_patterns=[r".*support.*", r".*complain.*", r".*billing.*issue.*"],
        description="Frequency of customer-initiated support or "
                     "complaint contact, regardless of channel.",
    ),
    CanonicalField(
        name="Satisfaction_Raw",
        exact_aliases=[
            "SatisfactionScore", "Overall_Satisfaction", "CreditScore",
            "Wait_Time_Satisfaction", "Staff_Satisfaction",
            "Provider_Rating",
        ],
        regex_patterns=[r".*satisfaction.*", r".*rating.*"],
        description="A satisfaction-adjacent score. NOTE: CreditScore is "
                     "a financial-health proxy, not a true satisfaction "
                     "measure — this distinction is preserved in "
                     "concepts.py via per-sector confidence weighting, "
                     "not silently merged here.",
    ),
    CanonicalField(
        name="Activity_Recency",
        exact_aliases=[
            "DaySinceLastOrder", "Days_Since_Last_Visit",
            "DaysSinceLastOrder",
        ],
        regex_patterns=[r".*since.*last.*", r".*recency.*"],
        description="Days since the customer last engaged "
                     "(order / visit / login).",
    ),
    CanonicalField(
        name="Engagement_Volume",
        exact_aliases=[
            "OrderCount", "Visits_Last_Year", "NumOfProducts",
            "NumberOfDeviceRegistered", "HourSpendOnApp",
        ],
        regex_patterns=[r".*count.*", r".*visits.*", r".*numof.*"],
        description="Volume of interaction or product usage — how much "
                     "the customer engages, distinct from how recently.",
    ),
    CanonicalField(
        name="Contract_Commitment",
        exact_aliases=["Contract", "PolicyType", "Insurance_Type"],
        regex_patterns=[r".*contract.*", r".*policy.*type.*"],
        description="The formal commitment structure — contract length "
                     "or policy type — used as a stability signal.",
    ),
    CanonicalField(
        name="Demographic_Risk",
        exact_aliases=["SeniorCitizen", "Age", "BMI"],
        regex_patterns=[r".*senior.*", r"^age$", r".*bmi.*"],
        description="Demographic attributes used as risk-adjacent "
                     "signals. Thresholds for 'high risk' are sector-"
                     "specific and applied in concepts.py.",
    ),
    CanonicalField(
        name="Auto_Payment_Flag",
        exact_aliases=["PaymentMethod", "PreferredPaymentMode", "HasCrCard"],
        regex_patterns=[r".*payment.*method.*", r".*payment.*mode.*"],
        description="Whether the customer's payment method implies "
                     "automatic/recurring billing.",
    ),
    CanonicalField(
        name="Active_Status",
        exact_aliases=["IsActiveMember"],
        regex_patterns=[r".*active.*member.*"],
        description="Explicit active/inactive flag where the source "
                     "dataset provides one directly.",
    ),
]

# Index by normalized alias for O(1) exact-match lookup
_EXACT_INDEX: dict[str, CanonicalField] = {}
for _field in CANONICAL_FIELDS:
    for _alias in _field._normalized_aliases():
        _EXACT_INDEX[_alias] = _field


# ══════════════════════════════════════════════════════════════════
# RESOLUTION RESULT
# ══════════════════════════════════════════════════════════════════

@dataclass
class ColumnResolution:
    """One row of the resolution report — what a raw column became."""
    raw_column: str
    canonical_field: str | None
    method: str          # 'exact' | 'regex' | 'unresolved'
    confidence: float    # 1.0 / 0.8 / 0.0


def resolve_schema(df: pd.DataFrame) -> tuple[pd.DataFrame, list[ColumnResolution]]:
    """
    Resolve every column in df to a canonical field name where possible.

    Returns
    -------
    resolved_df : pd.DataFrame
        Copy of df with resolvable columns renamed to their canonical
        field names. Unresolved columns are left untouched (still
        useful — feature_engineering.py may consult them directly for
        sector-specific logic that hasn't been generalised yet).

    resolutions : list[ColumnResolution]
        One entry per original column, recording how (or whether) it
        was resolved. This list is the input to the Coverage &
        Information Quality Engine's confidence weighting.
    """
    rename_map: dict[str, str] = {}
    resolutions: list[ColumnResolution] = []

    for raw_col in df.columns:
        normalized = _normalize(raw_col)

        # ── Strategy 1: exact match ─────────────────────────────
        if normalized in _EXACT_INDEX:
            canonical = _EXACT_INDEX[normalized]
            rename_map[raw_col] = canonical.name
            resolutions.append(ColumnResolution(
                raw_column=raw_col,
                canonical_field=canonical.name,
                method='exact',
                confidence=1.0,
            ))
            continue

        # ── Strategy 2: regex match ─────────────────────────────
        matched = False
        for canonical in CANONICAL_FIELDS:
            for pattern in canonical._compiled_patterns():
                if pattern.search(raw_col):
                    rename_map[raw_col] = canonical.name
                    resolutions.append(ColumnResolution(
                        raw_column=raw_col,
                        canonical_field=canonical.name,
                        method='regex',
                        confidence=0.8,
                    ))
                    matched = True
                    break
            if matched:
                break

        if not matched:
            resolutions.append(ColumnResolution(
                raw_column=raw_col,
                canonical_field=None,
                method='unresolved',
                confidence=0.0,
            ))

    resolved_df = df.rename(columns=rename_map)
    return resolved_df, resolutions


def resolution_summary(resolutions: list[ColumnResolution]) -> dict:
    """
    Aggregate a resolution report into the form the Coverage Engine
    and the CLI report want: counts per method, and the canonical
    fields that were never matched at all.
    """
    by_method = {'exact': 0, 'regex': 0, 'unresolved': 0}
    matched_fields = set()
    for r in resolutions:
        by_method[r.method] += 1
        if r.canonical_field:
            matched_fields.add(r.canonical_field)

    all_field_names = {f.name for f in CANONICAL_FIELDS}
    unmatched_fields = sorted(all_field_names - matched_fields)

    return {
        'exact_matches'     : by_method['exact'],
        'regex_matches'     : by_method['regex'],
        'unresolved_columns': by_method['unresolved'],
        'matched_fields'    : sorted(matched_fields),
        'unmatched_fields'  : unmatched_fields,
    }


# ══════════════════════════════════════════════════════════════════
# NOTE on fuzzy matching (intentionally not implemented)
# ══════════════════════════════════════════════════════════════════
# Fuzzy matching (e.g. Levenshtein/token-set ratio via rapidfuzz) was
# scoped out of this build deliberately:
#
#   1. Exact + regex already resolve every column seen in the four
#      production datasets (Telecom, Banking, E-commerce, Healthcare)
#      plus their known real-world variants. Fuzzy matching solves a
#      problem (typo'd or wildly renamed columns) that hasn't been
#      observed yet — adding it now is premature generalisation.
#   2. Fuzzy matches have unbounded false-positive risk: a low-quality
#      match silently renamed to a canonical field is *worse* than an
#      unresolved column, because it pollutes coverage scoring with
#      false confidence.
#
# To add it later WITHOUT touching any other module:
#   - add a `from rapidfuzz import fuzz` import here
#   - add a third strategy block in resolve_schema() after the regex
#     block, scored at confidence <= 0.5
#   - extend ColumnResolution.method to also accept 'fuzzy'
# Every downstream consumer (concepts.py, coverage.py) already reads
# `confidence` generically, so they require zero changes.

# ══════════════════════════════════════════════════════════════════
# SEMANTIC EXTENSION HOOKS (Version 6, Chunk 5, Part 3) — NOT WIRED IN
# ══════════════════════════════════════════════════════════════════
# Pure extension seams for Version 7. Nothing below is called from
# resolve_schema() today. Enabling this later means:
#   1. Fill in the bodies below.
#   2. Add ONE new strategy block inside resolve_schema(), after the
#      regex block and before "unresolved", calling
#      resolve_semantic_alias(). Exactly the plan already described in
#      the "NOTE on fuzzy matching" above.
# No other module needs to change — concepts.py, coverage.py,
# concept_confidence.py, and canonical_fields.py already read
# ColumnResolution.confidence generically, regardless of which
# strategy produced it.

def resolve_semantic_alias(
    raw_column: str,
    candidate_fields: list[CanonicalField] | None = None,
) -> "ColumnResolution | None":
    """
    Extension point for Version 7 semantic column matching.

    Currently a no-op — always returns None ("no semantic match
    attempted"), so resolve_schema()'s exact -> regex -> unresolved
    behavior is unaffected whether or not this is ever called.

    A real implementation would try, in order:
        1. future_embedding_match() — vector-similarity matching
        2. future_llm_resolution()  — LLM-assisted matching, last resort
    and return a ColumnResolution with method='semantic' at a
    confidence strictly below the regex tier (< 0.8), so a semantic
    match can never outrank a deterministic exact/regex hit.
    """
    return None


def future_embedding_match(
    raw_column: str,
    candidate_fields: list[CanonicalField],
) -> "ColumnResolution | None":
    """Placeholder — embedding-based column matching. Not implemented in V6."""
    raise NotImplementedError(
        "future_embedding_match is a Version 7 architecture placeholder. "
        "Not implemented in Version 6 — see resolve_semantic_alias()."
    )


def future_llm_resolution(
    raw_column: str,
    context: dict,
) -> "ColumnResolution | None":
    """Placeholder — LLM-assisted column matching. Not implemented in V6."""
    raise NotImplementedError(
        "future_llm_resolution is a Version 7 architecture placeholder. "
        "Not implemented in Version 6 — see resolve_semantic_alias()."
    )
