"""Canonical-first value access and feature provenance.

Feature builders use stable business identities from this module.  The only
place legacy dataset column names remain is ``LEGACY_COMPATIBILITY_CANDIDATES``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import numpy as np


@dataclass(frozen=True)
class CanonicalValueProvenance:
    concept: str
    source_column: str | None
    resolution_type: str
    confidence: float
    default_used: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class FeatureProvenance:
    feature: str
    concepts: tuple[str, ...]
    transformation: str
    status: str  # Resolved | Derived | Compatibility | Default | Intentional Neutral
    sources: tuple[CanonicalValueProvenance, ...]


# Business identity -> schema canonical field.  This is deliberately a small
# contract, not another alias registry.
CANONICAL_FIELD_BY_CONCEPT = {
    'CustomerTenure': 'Tenure_Raw', 'RecurringCost': 'Recurring_Cost',
    'RelationshipValue': 'Total_Spend', 'SupportContacts': 'Support_Contacts',
    'Satisfaction': 'Satisfaction_Raw', 'ActivityRecency': 'Activity_Recency',
    'EngagementVolume': 'Engagement_Volume', 'ContractCommitment': 'Contract_Commitment',
    'DemographicRisk': 'Demographic_Risk', 'AutoPayment': 'Auto_Payment_Flag',
    'ActiveStatus': 'Active_Status',
}

# Transitional adapter only.  Do not consume this mapping from feature
# builders: it preserves historical datasets/artifacts while canonical schema
# coverage is expanded independently.
LEGACY_COMPATIBILITY_CANDIDATES = {
    'CustomerTenure': ('tenure', 'Tenure', 'Tenure_Months'),
    'RecurringCost': ('MonthlyCharges', 'CashbackAmount', 'Avg_Out_Of_Pocket_Cost', 'MonthlyPremium'),
    'RelationshipValue': ('Balance',), 'SupportContacts': ('Complain', 'Billing_Issues'),
    'Satisfaction': ('SatisfactionScore', 'Overall_Satisfaction', 'CreditScore'),
    'ActivityRecency': ('DaySinceLastOrder', 'Days_Since_Last_Visit'),
    'EngagementVolume': ('OrderCount', 'Visits_Last_Year', 'FrequencyOfVisits', 'NumOfProducts'),
    'ContractCommitment': ('Contract',), 'DemographicRisk': ('SeniorCitizen', 'Age'),
    'AutoPayment': ('PaymentMethod', 'PreferredPaymentMode', 'HasCrCard'),
    'ActiveStatus': ('IsActiveMember',), 'CouponDependency': ('CouponUsed',),
    'ConvenienceDistance': ('WarehouseToHome', 'Distance_To_Facility_Miles'),
    'MissedAppointments': ('Missed_Appointments',), 'ReferralVolume': ('Referrals_Made',),
    'PortalUsage': ('Portal_Usage',), 'ServicePortfolio': (
        'PhoneService', 'MultipleLines', 'InternetService', 'OnlineSecurity',
        'OnlineBackup', 'DeviceProtection', 'TechSupport', 'StreamingTV', 'StreamingMovies',
    ),
    'CompositeSatisfaction': ('Overall_Satisfaction', 'Wait_Time_Satisfaction', 'Staff_Satisfaction', 'Provider_Rating'),
}


class CanonicalFeatureAccess:
    """Read canonical values first, with explicit legacy compatibility only."""
    def __init__(self, canonical_df: pd.DataFrame, raw_df: pd.DataFrame,
                 bindings: dict[str, CanonicalValueProvenance]):
        self.canonical_df, self.raw_df, self.bindings = canonical_df, raw_df, bindings
        self.used: dict[str, CanonicalValueProvenance] = {}

    def require(self, concept: str, default: float | str = 0.0) -> pd.Series:
        field = CANONICAL_FIELD_BY_CONCEPT.get(concept)
        binding = self.bindings.get(concept)
        if field and field in self.canonical_df.columns:
            value = self.canonical_df.loc[:, field]
            if isinstance(value, pd.DataFrame): value = value.bfill(axis=1).iloc[:, 0]
            self.used[concept] = binding or CanonicalValueProvenance(concept, field, 'canonical', 1.0)
            return value
        for name in LEGACY_COMPATIBILITY_CANDIDATES.get(concept, ()):
            if name in self.raw_df.columns:
                self.used[concept] = CanonicalValueProvenance(concept, name, 'compatibility', 0.0, reason='Canonical concept unavailable')
                return self.raw_df[name]
        self.used[concept] = CanonicalValueProvenance(concept, None, 'default', 0.0, True, 'Canonical concept unavailable')
        return pd.Series(default, index=self.canonical_df.index)

    def optional(self, concept: str) -> bool:
        self.require(concept)
        return not self.used[concept].default_used

    def normalized(self, concept: str, sector: str, norm_stats: dict | None,
                   default: float = 0.0, clip: bool = False) -> pd.Series:
        value = pd.to_numeric(self.require(concept, default), errors='coerce').fillna(default)
        provenance = self.used[concept]
        keys = [f'{sector}.{concept}']
        if provenance.source_column:
            keys.append(f'{sector}.{provenance.source_column}')
        maximum = next((float(norm_stats[k]) for k in keys if norm_stats and norm_stats.get(k)), None)
        if maximum is None:
            maximum = value.max()
            maximum = 1.0 if pd.isna(maximum) or maximum == 0 else float(maximum)
        result = value / maximum
        return result.clip(0, 1).fillna(default) if clip else result.fillna(default)

    def service_breadth(self) -> pd.Series:
        columns = LEGACY_COMPATIBILITY_CANDIDATES['ServicePortfolio']
        flags = [self.raw_df[column].astype(str).str.strip().str.lower().eq('yes').astype(float)
                 for column in columns if column in self.raw_df.columns]
        if not flags:
            self.used['ServicePortfolio'] = CanonicalValueProvenance('ServicePortfolio', None, 'default', 0.0, True, 'Canonical concept unavailable')
            return pd.Series(0.0, index=self.canonical_df.index)
        self.used['ServicePortfolio'] = CanonicalValueProvenance('ServicePortfolio', ','.join(c for c in columns if c in self.raw_df.columns), 'compatibility', 0.0, reason='Service portfolio is pending canonical schema support')
        return pd.concat(flags, axis=1).mean(axis=1)

    def mean_normalized(self, concept: str, sector: str, norm_stats: dict | None) -> pd.Series:
        columns = LEGACY_COMPATIBILITY_CANDIDATES[concept]
        scores = []
        for column in columns:
            if column in self.raw_df.columns:
                value = pd.to_numeric(self.raw_df[column], errors='coerce').fillna(0.0)
                maximum = float(norm_stats.get(f'{sector}.{column}', 0)) if norm_stats else 0.0
                maximum = maximum or value.max() or 1.0
                scores.append((value / maximum).clip(0, 1))
        if not scores:
            self.used[concept] = CanonicalValueProvenance(concept, None, 'default', 0.0, True, 'Canonical concept unavailable')
            return pd.Series(0.5, index=self.canonical_df.index)
        self.used[concept] = CanonicalValueProvenance(concept, ','.join(c for c in columns if c in self.raw_df.columns), 'compatibility', 0.0, reason='Composite source is pending canonical schema support')
        return pd.concat(scores, axis=1).mean(axis=1)
