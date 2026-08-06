import re
from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional, Tuple

import pandas as pd

from .semantic_schema import ColumnProfile
from .knowledge_packs import match_knowledge_pack
from .semantic_confidence import SemanticConfidence, from_pack_match

# ============================================================
# INTERNAL TAXONOMY -- hierarchical, domain separated
# ============================================================
# Each leaf concept contains its own metadata and a reference to a top-level domain.
# Business tags are derived from these concepts, NOT from raw feature tags.
_HIERARCHICAL_CONCEPT_TAXONOMY: Dict[str, Dict] = {
    "Financial": {
        "domain": "Financial",
        "children": {
            "Revenue": {
                "keywords": ["revenue", "income", "sale", "earnings"],
                "feature_tags": ["currency"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean", "median", "std"],
                "business_tags": ["revenue", "financial"],
                "metric": "Money",
                "dimensions": ["Financial", "Transactional"],
            },
            "Billing": {
                "keywords": ["billing", "bill", "invoice", "charge", "fee"],
                "feature_tags": ["currency"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean"],
                "business_tags": ["billing", "financial"],
                "metric": "Money",
                "dimensions": ["Financial", "Transactional"],
            },
            "Cost": {
                "keywords": ["cost", "expense", "price", "charge"],
                "feature_tags": ["currency"],
                "value_types": ["numeric"],
                "stat_patterns": [],
                "business_tags": ["cost", "financial"],
                "metric": "Money",
                "dimensions": ["Financial", "Transactional"],
            },
            "FinancialStrength": {
                "keywords": ["credit", "score", "balance", "salary", "cashback", "value", "investment"],
                "feature_tags": ["currency"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean"],
                "business_tags": ["financial", "strength", "value"],
                "metric": "Money",
                "dimensions": ["Financial", "Risk"],
            },
            "PaymentBehavior": {
                "keywords": ["payment", "card", "billing", "paperless"],
                "feature_tags": [],
                "value_types": ["categorical", "text", "boolean", "numeric"],
                "stat_patterns": [],
                "business_tags": ["payment", "billing", "financial"],
                "metric": "Category",
                "dimensions": ["Financial", "Behavioral"],
            },
            "RelationshipValue": {
                "keywords": ["total", "charges", "spend", "value", "lifetime", "clv", "ltv"],
                "feature_tags": ["currency"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean"],
                "business_tags": ["relationship", "value", "financial"],
                "metric": "Money",
                "dimensions": ["Financial", "Relationship"],
            },
            "FinancialActivity": {
                "keywords": ["transaction", "transfer", "debit", "credit", "withdrawal", "deposit", "activity"],
                "feature_tags": ["financial"],
                "value_types": ["numeric", "categorical"],
                "stat_patterns": ["count", "sum"],
                "business_tags": ["financial", "activity", "transaction"],
                "metric": "Count",
                "dimensions": ["Financial", "Transactional"],
            },
            "Spending": {
                "keywords": ["spend", "spending", "expense", "outlay", "purchase", "cost"],
                "feature_tags": ["currency", "financial"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean", "sum"],
                "business_tags": ["spending", "financial"],
                "metric": "Money",
                "dimensions": ["Financial", "Transactional"],
            },
            "Balance": {
                "keywords": ["balance", "funds", "available", "remaining", "account"],
                "feature_tags": ["currency", "financial"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean", "min", "max"],
                "business_tags": ["balance", "financial"],
                "metric": "Money",
                "dimensions": ["Financial"],
            },
        },
    },
    "Customer": {
        "domain": "Customer",
        "children": {
            "Demographics": {
                "keywords": ["age", "gender", "marital", "education", "income"],
                "feature_tags": [],
                "value_types": ["categorical", "text"],
                "stat_patterns": [],
                "business_tags": ["demographics", "customer"],
                "metric": "Category",
                "dimensions": ["Demographic"],
            },
            "Lifecycle": {
                "keywords": ["tenure", "duration", "age", "period"],
                "feature_tags": ["temporal"],
                "value_types": ["numeric", "datetime"],
                "stat_patterns": [],
                "business_tags": ["lifecycle", "customer"],
                "metric": "Duration",
                "dimensions": ["Relationship", "Lifecycle"],
            },
            "Engagement": {
                "keywords": ["visit", "usage", "login", "call", "click", "order", "purchase", "activity", "interaction", "engagement", "session"],
                "feature_tags": [],
                "value_types": ["numeric", "categorical"],
                "stat_patterns": [],
                "business_tags": ["engagement", "customer"],
                "metric": "Count",
                "dimensions": ["Behavioral"],
            },
            "CustomerLoyalty": {
                "keywords": ["loyalty", "loyal", "retention", "member", "membership", "tier", "vip", "stickiness", "advocate"],
                "feature_tags": ["behavioral"],
                "value_types": ["numeric", "categorical", "boolean"],
                "stat_patterns": [],
                "business_tags": ["loyalty", "retention", "customer"],
                "metric": "Score",
                "dimensions": ["Relationship", "Lifecycle"],
            },
            "PurchaseBehaviour": {
                "keywords": ["purchase", "order", "buy", "cart", "checkout", "shopping", "basket"],
                "feature_tags": ["behavioral"],
                "value_types": ["numeric", "categorical"],
                "stat_patterns": ["mean", "count"],
                "business_tags": ["purchase", "behaviour", "customer"],
                "metric": "Count",
                "dimensions": ["Behavioral", "Transactional"],
            },
            "DigitalEngagement": {
                "keywords": ["browsing", "browse", "session", "screen", "app", "online", "digital", "click", "scroll", "pageview", "dwell"],
                "feature_tags": ["behavioral", "temporal"],
                "value_types": ["numeric", "categorical"],
                "stat_patterns": [],
                "business_tags": ["engagement", "digital", "customer"],
                "metric": "Duration",
                "dimensions": ["Behavioral", "Interaction"],
            },
            "RelationshipStrength": {
                "keywords": ["relationship", "affinity", "attachment", "bond", "closeness", "tenure", "stickiness"],
                "feature_tags": ["behavioral"],
                "value_types": ["numeric", "categorical"],
                "stat_patterns": ["mean"],
                "business_tags": ["relationship", "strength", "customer"],
                "metric": "Score",
                "dimensions": ["Relationship", "Lifecycle"],
            },
            "Recency": {
                "keywords": ["since", "last", "recency", "recent"],
                "feature_tags": ["temporal"],
                "value_types": ["numeric", "datetime"],
                "stat_patterns": [],
                "business_tags": ["recency", "activity", "customer"],
                "metric": "Duration",
                "dimensions": ["Behavioral", "Lifecycle"],
            },
            "Frequency": {
                "keywords": ["frequency", "count", "visits", "orders", "recharge", "referrals"],
                "feature_tags": ["behavioral"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean"],
                "business_tags": ["frequency", "interaction", "customer"],
                "metric": "Count",
                "dimensions": ["Behavioral", "Interaction"],
            },
            "Location": {
                "keywords": ["state", "city", "region", "geography", "distance", "location"],
                "feature_tags": [],
                "value_types": ["numeric", "categorical", "text"],
                "stat_patterns": [],
                "business_tags": ["location", "access", "customer"],
                "metric": "Category",
                "dimensions": ["Location", "Accessibility"],
            },
            "ServicePortfolio": {
                "keywords": ["service", "internet", "phone", "security", "backup", "protection", "streaming", "device"],
                "feature_tags": [],
                "value_types": ["categorical", "text", "boolean", "numeric"],
                "stat_patterns": [],
                "business_tags": ["service", "portfolio", "usage"],
                "metric": "Category",
                "dimensions": ["Product", "Service"],
            },
            "HouseholdRelationship": {
                "keywords": ["partner", "dependent", "household", "family"],
                "feature_tags": [],
                "value_types": ["categorical", "text", "boolean", "numeric"],
                "stat_patterns": [],
                "business_tags": ["household", "relationship", "customer"],
                "metric": "Category",
                "dimensions": ["Relationship", "Demographic"],
            },
            "ContractCommitment": {
                "keywords": ["contract", "commitment", "term"],
                "feature_tags": [],
                "value_types": ["categorical", "text", "numeric"],
                "stat_patterns": [],
                "business_tags": ["contract", "commitment", "loyalty"],
                "metric": "Category",
                "dimensions": ["Relationship", "Product"],
            },
            "ServiceConnection": {
                "keywords": ["phone", "internet", "lines", "connection"],
                "feature_tags": [],
                "value_types": ["categorical", "text", "boolean", "numeric"],
                "stat_patterns": [],
                "business_tags": ["service", "connection", "usage"],
                "metric": "Category",
                "dimensions": ["Service", "Product"],
            },
            "ServiceAssurance": {
                "keywords": ["security", "backup", "protection", "support"],
                "feature_tags": [],
                "value_types": ["categorical", "text", "boolean", "numeric"],
                "stat_patterns": [],
                "business_tags": ["service", "assurance", "support"],
                "metric": "Category",
                "dimensions": ["Service", "Product"],
            },
            "MediaService": {
                "keywords": ["streaming", "movies", "television", "media"],
                "feature_tags": [],
                "value_types": ["categorical", "text", "boolean", "numeric"],
                "stat_patterns": [],
                "business_tags": ["service", "media", "usage"],
                "metric": "Category",
                "dimensions": ["Service", "Product"],
            },
        },
    },
    "Product": {
        "domain": "Product",
        "children": {
            "Subscription": {
                "keywords": ["subscription", "plan", "policy", "premium"],
                "feature_tags": ["currency"],
                "value_types": ["numeric"],
                "stat_patterns": [],
                "business_tags": ["subscription", "product"],
                "metric": "Money",
                "dimensions": ["Product"],
            },
            "ProductPreference": {
                "keywords": ["wishlist", "favorite", "favourite", "preference", "preferred", "category", "brand", "catalog", "sku", "item", "items", "product"],
                "feature_tags": [],
                "value_types": ["numeric", "categorical", "text", "boolean"],
                "stat_patterns": [],
                "business_tags": ["preference", "product", "customer"],
                "metric": "Count",
                "dimensions": ["Product", "Behavioral"],
            },
        },
    },
    "Risk": {
        "domain": "Risk",
        "children": {
            "Churn": {
                "keywords": ["churn", "attrition", "loss", "defection"],
                "feature_tags": [],
                "value_types": ["numeric", "categorical"],
                "stat_patterns": [],
                "business_tags": ["churn", "risk"],
                "metric": "Score",
                "dimensions": ["Risk"],
            },
        },
    },
    "Healthcare": {
        "domain": "Healthcare",
        "children": {
            "PatientCount": {
                "keywords": ["patient", "visit", "admission"],
                "feature_tags": [],
                "value_types": ["numeric"],
                "stat_patterns": ["mean", "median"],
                "business_tags": ["patient", "healthcare"],
                "metric": "Count",
                "dimensions": ["Healthcare"],
            },
            "TreatmentCost": {
                "keywords": ["treatment", "procedure", "cost", "expense"],
                "feature_tags": ["currency"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean"],
                "business_tags": ["treatment", "financial", "healthcare"],
                "metric": "Money",
                "dimensions": ["Healthcare", "Financial"],
            },
            "CareSatisfaction": {
                "keywords": ["satisfaction", "wait", "staff", "provider", "rating"],
                "feature_tags": [],
                "value_types": ["numeric"],
                "stat_patterns": ["mean"],
                "business_tags": ["care", "satisfaction", "healthcare"],
                "metric": "Score",
                "dimensions": ["CustomerExperience", "Healthcare"],
            },
            "AppointmentBehaviour": {
                "keywords": ["appointment", "schedule", "booking", "noshow", "cancel", "cancellation", "reschedule", "slot"],
                "feature_tags": ["temporal", "behavioral"],
                "value_types": ["numeric", "categorical", "datetime", "boolean"],
                "stat_patterns": ["count"],
                "business_tags": ["appointment", "behaviour", "healthcare"],
                "metric": "Count",
                "dimensions": ["Healthcare", "Behavioral"],
            },
        },
    },
    "Insurance": {
        "domain": "Insurance",
        "children": {
            "PolicyCount": {
                "keywords": ["policy", "coverage", "holder"],
                "feature_tags": [],
                "value_types": ["numeric"],
                "stat_patterns": ["mean"],
                "business_tags": ["policy", "insurance"],
                "metric": "Count",
                "dimensions": ["Insurance"],
            },
            "ClaimAmount": {
                "keywords": ["claim", "payout", "amount", "settlement"],
                "feature_tags": ["currency"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean", "std"],
                "business_tags": ["claim", "financial", "insurance"],
                "metric": "Money",
                "dimensions": ["Insurance", "Financial"],
            },
        },
    },
    "Banking": {
        "domain": "Banking",
        "children": {
            "AccountBalance": {
                "keywords": ["balance", "account", "funds"],
                "feature_tags": ["currency"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean", "min", "max"],
                "business_tags": ["balance", "banking"],
                "metric": "Money",
                "dimensions": ["Banking", "Financial"],
            },
            "TransactionCount": {
                "keywords": ["transaction", "payment", "transfer"],
                "feature_tags": [],
                "value_types": ["numeric"],
                "stat_patterns": ["count"],
                "business_tags": ["transaction", "banking"],
                "metric": "Count",
                "dimensions": ["Banking"],
            },
        },
    },
    "Retail": {
        "domain": "Retail",
        "children": {
            "SalesRevenue": {
                "keywords": ["sales", "revenue", "turnover"],
                "feature_tags": ["currency"],
                "value_types": ["numeric"],
                "stat_patterns": ["mean", "sum"],
                "business_tags": ["sales", "retail"],
                "metric": "Money",
                "dimensions": ["Retail", "Financial"],
            },
            "CustomerCount": {
                "keywords": ["customer", "shopper", "visitor"],
                "feature_tags": [],
                "value_types": ["numeric"],
                "stat_patterns": ["mean"],
                "business_tags": ["customer", "retail"],
                "metric": "Count",
                "dimensions": ["Retail"],
            },
        },
    },
    "Telecom": {
        "domain": "Telecom",
        "children": {
            "CallDuration": {
                "keywords": ["call", "duration", "minutes"],
                "feature_tags": [],
                "value_types": ["numeric"],
                "stat_patterns": ["mean", "sum"],
                "business_tags": ["call", "telecom"],
                "metric": "Duration",
                "dimensions": ["Telecom"],
            },
            "DataUsage": {
                "keywords": ["data", "usage", "gb", "mb"],
                "feature_tags": [],
                "value_types": ["numeric"],
                "stat_patterns": ["mean", "sum"],
                "business_tags": ["data", "telecom"],
                "metric": "Count",
                "dimensions": ["Telecom"],
            },
            "NetworkUsage": {
                "keywords": ["network", "bandwidth", "signal", "coverage", "roaming", "sms", "voice", "minutes", "throughput"],
                "feature_tags": [],
                "value_types": ["numeric", "categorical"],
                "stat_patterns": ["mean", "sum"],
                "business_tags": ["network", "usage", "telecom"],
                "metric": "Count",
                "dimensions": ["Telecom", "Behavioral"],
            },
        },
    },
    "Support": {"domain": "Support", "children": {
        "SupportFriction": {
            "keywords": ["complaint", "complain", "issue", "ticket", "support"],
            "feature_tags": ["behavioral"],
            "value_types": ["numeric", "categorical", "boolean"],
            "stat_patterns": [],
            "business_tags": ["support", "friction", "interaction"],
            "metric": "Count",
            "dimensions": ["CustomerSupport", "Interaction"],
        },
        "ServiceQuality": {
            "keywords": ["quality", "satisfaction", "rating", "score", "nps", "csat", "experience", "reliability"],
            "feature_tags": [],
            "value_types": ["numeric", "categorical"],
            "stat_patterns": ["mean"],
            "business_tags": ["quality", "service", "customer"],
            "metric": "Score",
            "dimensions": ["CustomerExperience", "Service"],
        },
        "ReturnBehaviour": {
            "keywords": ["return", "refund", "exchange", "rma", "reverse"],
            "feature_tags": ["behavioral"],
            "value_types": ["numeric", "categorical", "boolean"],
            "stat_patterns": ["count"],
            "business_tags": ["return", "behaviour", "support"],
            "metric": "Count",
            "dimensions": ["Behavioral", "Transactional"],
        },
    }},
    "Operations": {"domain": "Operations", "children": {}},
    "Marketing": {"domain": "Marketing", "children": {
        "RewardProgram": {
            "keywords": ["reward", "cashback", "coupon", "discount", "promo", "promotion", "points", "plus", "program", "voucher", "rebate", "membership"],
            "feature_tags": ["currency", "behavioral"],
            "value_types": ["numeric", "categorical", "boolean"],
            "stat_patterns": [],
            "business_tags": ["reward", "marketing", "loyalty"],
            "metric": "Money",
            "dimensions": ["Marketing", "Relationship"],
        },
    }},
}

# ------------------------------------------------------------
# ONTOLOGY FAMILY MAPPING -- derived from _HIERARCHICAL_CONCEPT_TAXONOMY
# ------------------------------------------------------------
_CONCEPT_FAMILY_CACHE: Dict[str, str] = {}

def _build_concept_family_cache() -> Dict[str, str]:
    """Map every concept to its top-level ontology family (domain key)."""
    cache: Dict[str, str] = {}
    for domain_key, domain_val in _HIERARCHICAL_CONCEPT_TAXONOMY.items():
        family = domain_val.get("domain", domain_key)
        for concept in domain_val.get("children", {}):
            cache[concept] = family
    return cache

_CONCEPT_FAMILY_CACHE = _build_concept_family_cache()

def _concept_to_family(concept: str) -> str:
    """Return the ontology family for a concept, e.g. 'PatientCount' -> 'Healthcare'."""
    return _CONCEPT_FAMILY_CACHE.get(concept, "General")


# ------------------------------------------------------------
# SECTOR KEYWORD HEURISTICS -- dataset-independent sector hints
# ------------------------------------------------------------
# These are general business terms, NOT company or dataset names.
_SECTOR_KEYWORDS: Dict[str, set] = {
    "Healthcare": {
        "patient", "diagnosis", "admission", "doctor", "hospital", "medicine",
        "lab", "laboratory", "surgery", "clinic", "appointment", "prescription",
        "pharmacy", "nurse", "treatment", "therapy", "ward", "discharge",
        "disease", "chronic", "emergency", "speciality", "insurance_provider",
        "outstanding", "feedback_rating", "telemedicine",
    },
    "Banking": {
        "atm", "branch", "account", "loan", "credit", "debit", "mortgage",
        "deposit", "withdrawal", "transaction", "balance", "bank", "savings",
        "checking", "overdraft", "interest", "card", "statement", "credit_score",
    },
    "Telecom": {
        "call", "data", "sms", "recharge", "signal", "network", "roaming",
        "broadband", "sim", "plan", "voice", "minutes", "usage_gb", "arpu",
        "auto_pay", "drops", "ott", "subscription", "device_type",
    },
    "Ecommerce": {
        "order", "cart", "wishlist", "checkout", "product", "coupon", "delivery",
        "review", "rating", "browse", "browsing", "return", "favorite_category",
        "app_sessions", "cart_abandonment", "reward_points", "delivery_time",
        "prime", "loyalty_member", "complaint", "account_age",
    },
    "Insurance": {
        "policy", "claim", "premium", "coverage", "deductible", "beneficiary",
        "holder", "payout", "settlement", "insurer",
    },
}


# ------------------------------------------------------------
# SEMANTIC CONTEXT -- dataset-level fingerprint
# ------------------------------------------------------------
@dataclass
class DatasetFingerprint:
    """Captures the aggregate semantic profile of a dataset."""
    sector_scores: Dict[str, float] = field(default_factory=dict)
    dominant_sector: str = "General"
    sector_confidence: float = 0.0
    family_distribution: Dict[str, int] = field(default_factory=dict)
    dominant_family: str = "General"
    family_confidence: float = 0.0
    domain_distribution: Dict[str, int] = field(default_factory=dict)
    dominant_domain: str = "General"
    dimension_distribution: Dict[str, int] = field(default_factory=dict)
    dominant_dimension: str = "General"
    concept_frequency: Dict[str, int] = field(default_factory=dict)
    total_columns: int = 0

    def is_outlier_family(self, concept: str) -> bool:
        """True if concept's ontology family differs from the dataset's dominant family."""
        concept_family = _concept_to_family(concept)
        return concept_family != self.dominant_family and concept_family != "General"


# ------------------------------------------------------------
# DIAGNOSTIC DATA CLASSES -- explainable context adjustments
# ------------------------------------------------------------
@dataclass
class ComponentScores:
    """Breakdown of individual scoring components for a candidate concept."""
    keyword_score: float = 0.0
    feature_score: float = 0.0
    value_type_score: float = 0.0
    indicator_score: float = 0.0
    statistical_score: float = 0.0
    sector_prior: float = 0.0
    dataset_context: float = 0.0
    ontology_consistency: float = 0.0
    outlier_penalty: float = 0.0
    raw_signal: float = 0.0
    final_score: float = 0.0

    def explain_components(self) -> List[str]:
        parts = [
            f"signal={self.raw_signal:.3f}",
            f"sector={self.sector_prior:+.3f}",
            f"context={self.dataset_context:+.3f}",
            f"ontology={self.ontology_consistency:+.3f}",
            f"outlier={self.outlier_penalty:+.3f}",
            f"final={self.final_score:.3f}",
        ]
        return parts


@dataclass
class ContextAdjustment:
    """One explainable adjustment to a candidate's score."""
    component: str
    delta: float
    reason: str


# ------------------------------------------------------------
# Evidence dataclass -- central reasoning object (private)
# ------------------------------------------------------------
@dataclass(frozen=True)
class BusinessConceptEvidence:
    candidate_concepts: List[str]
    concept_scores: Dict[str, float]
    matched_keywords: Dict[str, List[str]]
    feature_evidence: List[str]
    feature_scores: Dict[str, float]
    value_type: Optional[str]
    value_type_score: Dict[str, float]
    indicator_scores: Dict[str, float]
    statistical_evidence: Dict[str, Any]
    statistical_scores: Dict[str, float]
    conflict_signals: List[str]
    reasoning_steps: List[str]
    signal_strength: float

# ------------------------------------------------------------
# Scoring weights -- deterministic (user approved)
# ------------------------------------------------------------
_WEIGHT_KEYWORD = 0.30
_WEIGHT_FEATURE = 0.20
_WEIGHT_VALUETYPE = 0.15
_WEIGHT_INDICATOR = 0.15
_WEIGHT_STAT = 0.15
_WEIGHT_CONFLICT = -0.10
_WEIGHT_AMBIGUITY = -0.05
_SIGNAL_CANDIDATE_THRESHOLD = 0.35
_MIN_PREFIX_LEN = 3
_MIN_SUBSTRING_LEN = 4

# Context-aware additive weights (not percentages -- additive to raw signal)
_SECTOR_PRIOR_BOOST = 0.15
_DATASET_CONTEXT_BOOST = 0.10
_ONTOLOGY_CONSISTENCY_BOOST = 0.05
_OUTLIER_FAMILY_PENALTY = -0.20

# Helper: flatten taxonomy into concept -> meta mapping
def _flatten_taxonomy() -> Dict[str, Dict]:
    flat: Dict[str, Dict] = {}
    for domain_key, domain_val in _HIERARCHICAL_CONCEPT_TAXONOMY.items():
        children = domain_val.get("children", {})
        for concept, meta in children.items():
            meta_copy = dict(meta)
            meta_copy["domain"] = domain_val.get("domain", domain_key)
            flat[concept] = meta_copy
    return flat

_FLAT_TAXONOMY = _flatten_taxonomy()

# ------------------------------------------------------------
# Lexical matching -- deterministic, no external NLP
# ------------------------------------------------------------
def _singularize(token: str) -> str:
    """Lightweight English singularization for token/keyword alignment."""
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("es") and len(token) > 4:
        stem = token[:-2]
        if stem.endswith("sh") or stem.endswith("ch") or stem.endswith("ss"):
            return stem
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token

def _token_matches_keyword(token: str, keyword: str) -> bool:
    """Match tokens to keywords via exact, plural, prefix, and safe substring rules."""
    token_l = token.lower()
    keyword_l = keyword.lower()
    if token_l == keyword_l:
        return True
    if _singularize(token_l) == keyword_l or token_l == _singularize(keyword_l):
        return True
    if len(keyword_l) >= _MIN_PREFIX_LEN and (token_l.startswith(keyword_l) or keyword_l.startswith(token_l)):
        return True
    if len(keyword_l) >= _MIN_SUBSTRING_LEN and keyword_l in token_l:
        return True
    if len(token_l) >= _MIN_SUBSTRING_LEN and token_l in keyword_l:
        return True
    return False

def _find_matched_keywords(meta: Dict, tokens: List[str]) -> List[str]:
    """Return taxonomy keywords that match any column token."""
    matched: List[str] = []
    for keyword in meta.get("keywords", []):
        if any(_token_matches_keyword(token, keyword) for token in tokens):
            matched.append(keyword.lower())
    return matched

def _keyword_match_score(concept: str, meta: Dict, profile: ColumnProfile) -> float:
    kw_set = set(k.lower() for k in meta.get("keywords", []))
    if not kw_set:
        return 0.0
    matches = _find_matched_keywords(meta, profile.tokens)
    return len(set(matches)) / len(kw_set)

def _feature_tag_score(concept: str, meta: Dict, profile: ColumnProfile) -> float:
    ft_set = set(meta.get("feature_tags", []))
    detected = set(profile.detected_features)
    if not ft_set:
        return 0.0
    return len(ft_set & detected) / len(ft_set)

def _value_type_score(concept: str, meta: Dict, profile: ColumnProfile) -> float:
    allowed = set(meta.get("value_types", []))
    vt = profile.value_type
    if not vt or not allowed:
        return 0.0
    return 1.0 if vt in allowed else 0.0

def _indicator_score(concept: str, meta: Dict, profile: ColumnProfile) -> float:
    score = 0.0
    total = 0
    if "temporal" in meta.get("feature_tags", []):
        total += 1
        score += 1.0 if profile.temporal_indicators else 0.0
    if "currency" in meta.get("feature_tags", []):
        total += 1
        score += 1.0 if profile.financial_indicators else 0.0
    if "behavioral" in meta.get("feature_tags", []):
        total += 1
        score += 1.0 if profile.behavioral_indicators else 0.0
    return (score / total) if total else 0.0

def _statistical_score(concept: str, meta: Dict, profile: ColumnProfile) -> float:
    required = set(meta.get("stat_patterns", []))
    present = {k for k in profile.statistical_profile.keys() if k in {"mean", "median", "std", "min", "max", "sum", "count"}}
    if not required:
        return 0.0
    return len(required & present) / len(required)

def _conflict_signals(concept: str, meta: Dict, profile: ColumnProfile) -> List[str]:
    signals = []
    vt = profile.value_type
    if vt and vt not in meta.get("value_types", []):
        signals.append(f"Value type mismatch (expected {meta.get('value_types')} got {vt})")
    return signals

def _metadata_signal_score(meta: Dict, profile: ColumnProfile) -> float:
    """Non-keyword evidence from feature tags, value types, indicators, and stats."""
    ft = _feature_tag_score("", meta, profile)
    vt = _value_type_score("", meta, profile)
    ind = _indicator_score("", meta, profile)
    st = _statistical_score("", meta, profile)
    return (
        _WEIGHT_FEATURE * ft
        + _WEIGHT_VALUETYPE * vt
        + _WEIGHT_INDICATOR * ind
        + _WEIGHT_STAT * st
    )

def _ontology_related(concept_a: str, concept_b: str) -> bool:
    """True when two concepts share a domain or overlapping customer dimensions."""
    meta_a = _FLAT_TAXONOMY.get(concept_a, {})
    meta_b = _FLAT_TAXONOMY.get(concept_b, {})
    if meta_a.get("domain") == meta_b.get("domain"):
        return True
    dims_a = set(meta_a.get("dimensions", []))
    dims_b = set(meta_b.get("dimensions", []))
    return bool(dims_a & dims_b)

def _is_candidate_concept(meta: Dict, profile: ColumnProfile) -> Tuple[bool, List[str]]:
    """Promote a concept when keyword or strong metadata evidence is present."""
    keyword_matches = _find_matched_keywords(meta, profile.tokens)
    if keyword_matches:
        return True, keyword_matches
    metadata_score = _metadata_signal_score(meta, profile)
    if metadata_score >= _SIGNAL_CANDIDATE_THRESHOLD and _value_type_score("", meta, profile) > 0:
        return True, []
    return False, []

def _score_concept(concept: str, meta: Dict, profile: ColumnProfile) -> Dict:
    kw = _keyword_match_score(concept, meta, profile)
    ft = _feature_tag_score(concept, meta, profile)
    vt = _value_type_score(concept, meta, profile)
    ind = _indicator_score(concept, meta, profile)
    st = _statistical_score(concept, meta, profile)
    conflicts = _conflict_signals(concept, meta, profile)
    raw = (
        _WEIGHT_KEYWORD * kw
        + _WEIGHT_FEATURE * ft
        + _WEIGHT_VALUETYPE * vt
        + _WEIGHT_INDICATOR * ind
        + _WEIGHT_STAT * st
        + _WEIGHT_CONFLICT * (1.0 if conflicts else 0.0)
    )
    reasoning = [
        f"Keyword match={kw:.3f}",
        f"Feature tags={ft:.3f}",
        f"Value type={vt:.3f}",
        f"Indicators={ind:.3f}",
        f"Statistical={st:.3f}",
    ]
    if conflicts:
        reasoning.append(f"Conflicts={'; '.join(conflicts)}")
    return {"score": max(0.0, min(1.0, raw)), "reasoning": reasoning, "conflicts": conflicts}


# ------------------------------------------------------------
# CONTEXT-AWARE SCORING -- sector prior, dataset context, ontology consistency
# ------------------------------------------------------------
def _detect_sector_from_tokens(tokens: List[str]) -> Tuple[str, float]:
    """Score column's tokens against sector keyword sets. Returns (best_sector, confidence)."""
    best_sector = "General"
    best_score = 0.0
    token_set = set(t.lower() for t in tokens)
    for sector, keywords in _SECTOR_KEYWORDS.items():
        matches = token_set & keywords
        if matches:
            score = len(matches) / len(keywords)
            if score > best_score:
                best_score = score
                best_sector = sector
    return best_sector, best_score


def _compute_dataset_fingerprint(preliminary: List[Tuple[ColumnProfile, Dict, BusinessConceptEvidence]]) -> DatasetFingerprint:
    """Build a dataset fingerprint from preliminary column analyses."""
    profiles = [p for p, _, _ in preliminary]
    evidence_list = [e for _, _, e in preliminary]

    # 1. Sector detection: aggregate sector keywords across all column tokens
    sector_hits: Dict[str, int] = {}
    for profile in profiles:
        for token in profile.tokens:
            for sector, keywords in _SECTOR_KEYWORDS.items():
                if token.lower() in keywords:
                    sector_hits[sector] = sector_hits.get(sector, 0) + 1
    total_hits = sum(sector_hits.values()) or 1
    sector_scores = {s: c / total_hits for s, c in sector_hits.items()}
    dominant_sector = max(sector_scores, key=sector_scores.get) if sector_scores else "General"
    sector_confidence = sector_scores.get(dominant_sector, 0.0)

    # 2. Ontology family distribution from preliminary concept scores
    family_dist: Dict[str, int] = {}
    for ev in evidence_list:
        for concept, score in ev.concept_scores.items():
            if score > 0:
                family = _concept_to_family(concept)
                family_dist[family] = family_dist.get(family, 0) + 1
    dominant_family = max(family_dist, key=family_dist.get) if family_dist else "General"
    total_family = sum(family_dist.values()) or 1
    family_confidence = family_dist.get(dominant_family, 0) / total_family

    # 3. Domain distribution from preliminary top concepts
    domain_dist: Dict[str, int] = {}
    for ev in evidence_list:
        if ev.candidate_concepts:
            top = max(ev.candidate_concepts, key=lambda c: ev.concept_scores.get(c, 0.0))
            meta = _FLAT_TAXONOMY.get(top, {})
            domain = meta.get("domain", "General")
            domain_dist[domain] = domain_dist.get(domain, 0) + 1
    dominant_domain = max(domain_dist, key=domain_dist.get) if domain_dist else "General"

    # 4. Dimension distribution
    dim_dist: Dict[str, int] = {}
    for ev in evidence_list:
        if ev.candidate_concepts:
            top = max(ev.candidate_concepts, key=lambda c: ev.concept_scores.get(c, 0.0))
            meta = _FLAT_TAXONOMY.get(top, {})
            for d in meta.get("dimensions", []):
                dim_dist[d] = dim_dist.get(d, 0) + 1
    dominant_dim = max(dim_dist, key=dim_dist.get) if dim_dist else "General"

    # 5. Concept frequency
    concept_freq: Dict[str, int] = {}
    for ev in evidence_list:
        if ev.candidate_concepts:
            top = max(ev.candidate_concepts, key=lambda c: ev.concept_scores.get(c, 0.0))
            concept_freq[top] = concept_freq.get(top, 0) + 1

    return DatasetFingerprint(
        sector_scores=sector_scores,
        dominant_sector=dominant_sector,
        sector_confidence=sector_confidence,
        family_distribution=family_dist,
        dominant_family=dominant_family,
        family_confidence=family_confidence,
        domain_distribution=domain_dist,
        dominant_domain=dominant_domain,
        dimension_distribution=dim_dist,
        dominant_dimension=dominant_dim,
        concept_frequency=concept_freq,
        total_columns=len(profiles),
    )


def _compute_sector_prior(concept: str, meta: Dict, fingerprint: DatasetFingerprint) -> float:
    """Boost if concept's domain matches detected sector. Additive boost, not multiplicative."""
    domain = meta.get("domain", "General")
    if fingerprint.sector_scores:
        if domain == fingerprint.dominant_sector:
            return _SECTOR_PRIOR_BOOST * fingerprint.sector_confidence
    return 0.0


def _compute_dataset_context_score(concept: str, meta: Dict, fingerprint: DatasetFingerprint) -> float:
    """Boost if concept's domain aligns with the dataset's dominant domain."""
    domain = meta.get("domain", "General")
    if domain == fingerprint.dominant_domain:
        return _DATASET_CONTEXT_BOOST
    # Partial boost if domain is in the top-3 of domain distribution
    sorted_domains = sorted(fingerprint.domain_distribution.items(), key=lambda x: -x[1])
    if len(sorted_domains) >= 3 and domain in (d for d, _ in sorted_domains[:3]):
        return _DATASET_CONTEXT_BOOST * 0.5
    return 0.0


def _compute_ontology_consistency(concept: str, meta: Dict, fingerprint: DatasetFingerprint) -> float:
    """Boost if concept's ontology family matches the dataset's dominant family."""
    family = _concept_to_family(concept)
    if family == fingerprint.dominant_family:
        return _ONTOLOGY_CONSISTENCY_BOOST
    # Check if family is present in the dataset at all
    if family in fingerprint.family_distribution:
        return _ONTOLOGY_CONSISTENCY_BOOST * 0.3
    return 0.0


def _compute_outlier_penalty(concept: str, meta: Dict, fingerprint: DatasetFingerprint) -> float:
    """Penalize if concept belongs to a completely different family than the dataset."""
    family = _concept_to_family(concept)
    if family == "General":
        return 0.0
    if family != fingerprint.dominant_family and family not in fingerprint.family_distribution:
        return _OUTLIER_FAMILY_PENALTY
    if family != fingerprint.dominant_family:
        # Present but not dominant -- mild penalty
        return _OUTLIER_FAMILY_PENALTY * 0.5
    return 0.0


def _score_concept_with_context(
    concept: str,
    meta: Dict,
    profile: ColumnProfile,
    fingerprint: Optional[DatasetFingerprint],
) -> Dict:
    """Score a concept combining raw signal with context-aware adjustments."""
    base = _score_concept(concept, meta, profile)
    raw_score = base["score"]
    scores = ComponentScores(
        keyword_score=_keyword_match_score(concept, meta, profile),
        feature_score=_feature_tag_score(concept, meta, profile),
        value_type_score=_value_type_score(concept, meta, profile),
        indicator_score=_indicator_score(concept, meta, profile),
        statistical_score=_statistical_score(concept, meta, profile),
        raw_signal=raw_score,
    )
    adjustments: List[ContextAdjustment] = []

    if fingerprint is not None and fingerprint.total_columns > 0:
        sector_prior = _compute_sector_prior(concept, meta, fingerprint)
        scores.sector_prior = sector_prior
        if sector_prior != 0.0:
            adjustments.append(ContextAdjustment(
                "sector_prior", sector_prior,
                f"Domain '{meta.get('domain')}' matches detected sector '{fingerprint.dominant_sector}'"
            ))

        dataset_ctx = _compute_dataset_context_score(concept, meta, fingerprint)
        scores.dataset_context = dataset_ctx
        if dataset_ctx != 0.0:
            adjustments.append(ContextAdjustment(
                "dataset_context", dataset_ctx,
                f"Domain '{meta.get('domain')}' aligns with dataset's dominant domain '{fingerprint.dominant_domain}'"
            ))

        ontology_cons = _compute_ontology_consistency(concept, meta, fingerprint)
        scores.ontology_consistency = ontology_cons
        if ontology_cons != 0.0:
            family = _concept_to_family(concept)
            adjustments.append(ContextAdjustment(
                "ontology_consistency", ontology_cons,
                f"Concept family '{family}' consistent with dataset's dominant family '{fingerprint.dominant_family}'"
            ))

        outlier_pen = _compute_outlier_penalty(concept, meta, fingerprint)
        scores.outlier_penalty = outlier_pen
        if outlier_pen != 0.0:
            family = _concept_to_family(concept)
            adjustments.append(ContextAdjustment(
                "outlier_penalty", outlier_pen,
                f"Concept family '{family}' is an outlier in a dataset dominated by '{fingerprint.dominant_family}'"
            ))

    final_score = (
        scores.raw_signal
        + scores.sector_prior
        + scores.dataset_context
        + scores.ontology_consistency
        + scores.outlier_penalty
    )
    scores.final_score = max(0.0, min(1.0, final_score))

    reasoning = base["reasoning"][:]
    for adj in adjustments:
        reasoning.append(f"[context] {adj.component}={adj.delta:+.3f}: {adj.reason}")

    return {
        "score": scores.final_score,
        "reasoning": reasoning,
        "conflicts": base["conflicts"],
        "components": scores,
        "adjustments": adjustments,
    }


# ------------------------------------------------------------
# Evidence extraction -- builds the enriched evidence object
# ------------------------------------------------------------
def _extract_concept_evidence(profile: ColumnProfile) -> BusinessConceptEvidence:
    candidate_concepts: List[str] = []
    matched_keywords: Dict[str, List[str]] = {}
    concept_scores: Dict[str, float] = {}
    feature_scores: Dict[str, float] = {}
    value_type_score: Dict[str, float] = {}
    indicator_scores: Dict[str, float] = {}
    statistical_scores: Dict[str, float] = {}
    conflict_signals: List[str] = []
    reasoning_steps: List[str] = []
    for concept, meta in _FLAT_TAXONOMY.items():
        is_candidate, matches = _is_candidate_concept(meta, profile)
        if not is_candidate:
            continue
        candidate_concepts.append(concept)
        if matches:
            matched_keywords[concept] = matches
    for concept in candidate_concepts:
        meta = _FLAT_TAXONOMY[concept]
        result = _score_concept(concept, meta, profile)
        concept_scores[concept] = result["score"]
        reasoning_steps.extend([f"[{concept}] " + r for r in result["reasoning"]])
        conflict_signals.extend([f"[{concept}] " + c for c in result["conflicts"]])
        feature_scores[concept] = _feature_tag_score(concept, meta, profile)
        value_type_score[concept] = _value_type_score(concept, meta, profile)
        indicator_scores[concept] = _indicator_score(concept, meta, profile)
        statistical_scores[concept] = _statistical_score(concept, meta, profile)
    total_possible = sum(len(meta.get("keywords", [])) for meta in _FLAT_TAXONOMY.values())
    total_matched = sum(len(kws) for kws in matched_keywords.values())
    signal_strength = total_matched / total_possible if total_possible else 0.0
    return BusinessConceptEvidence(
        candidate_concepts=candidate_concepts,
        concept_scores=concept_scores,
        matched_keywords=matched_keywords,
        feature_evidence=profile.detected_features,
        feature_scores=feature_scores,
        value_type=profile.value_type,
        value_type_score=value_type_score,
        indicator_scores=indicator_scores,
        statistical_evidence=profile.statistical_profile,
        statistical_scores=statistical_scores,
        conflict_signals=conflict_signals,
        reasoning_steps=reasoning_steps,
        signal_strength=signal_strength,
    )


def _extract_concept_evidence_with_context(
    profile: ColumnProfile,
    fingerprint: Optional[DatasetFingerprint],
) -> BusinessConceptEvidence:
    """Evidence extraction using context-aware scoring when a dataset fingerprint is available."""
    candidate_concepts: List[str] = []
    matched_keywords: Dict[str, List[str]] = {}
    concept_scores: Dict[str, float] = {}
    component_scores: Dict[str, ComponentScores] = {}
    all_adjustments: Dict[str, List[ContextAdjustment]] = {}
    feature_scores: Dict[str, float] = {}
    value_type_score: Dict[str, float] = {}
    indicator_scores: Dict[str, float] = {}
    statistical_scores: Dict[str, float] = {}
    conflict_signals: List[str] = []
    reasoning_steps: List[str] = []

    for concept, meta in _FLAT_TAXONOMY.items():
        is_candidate, matches = _is_candidate_concept(meta, profile)
        if not is_candidate:
            continue
        candidate_concepts.append(concept)
        if matches:
            matched_keywords[concept] = matches

    for concept in candidate_concepts:
        meta = _FLAT_TAXONOMY[concept]
        result = _score_concept_with_context(concept, meta, profile, fingerprint)
        concept_scores[concept] = result["score"]
        component_scores[concept] = result.get("components", ComponentScores())
        all_adjustments[concept] = result.get("adjustments", [])
        reasoning_steps.extend([f"[{concept}] " + r for r in result["reasoning"]])
        conflict_signals.extend([f"[{concept}] " + c for c in result["conflicts"]])
        feature_scores[concept] = _feature_tag_score(concept, meta, profile)
        value_type_score[concept] = _value_type_score(concept, meta, profile)
        indicator_scores[concept] = _indicator_score(concept, meta, profile)
        statistical_scores[concept] = _statistical_score(concept, meta, profile)

    total_possible = sum(len(meta.get("keywords", [])) for meta in _FLAT_TAXONOMY.values())
    total_matched = sum(len(kws) for kws in matched_keywords.values())
    signal_strength = total_matched / total_possible if total_possible else 0.0

    return BusinessConceptEvidence(
        candidate_concepts=candidate_concepts,
        concept_scores=concept_scores,
        matched_keywords=matched_keywords,
        feature_evidence=profile.detected_features,
        feature_scores=feature_scores,
        value_type=profile.value_type,
        value_type_score=value_type_score,
        indicator_scores=indicator_scores,
        statistical_evidence=profile.statistical_profile,
        statistical_scores=statistical_scores,
        conflict_signals=conflict_signals,
        reasoning_steps=reasoning_steps,
        signal_strength=signal_strength,
    )

# ------------------------------------------------------------
# Domain, Metric, Customer-Dimension classifiers -- score-based
# ------------------------------------------------------------
def _classify_domain(evidence: BusinessConceptEvidence) -> str:
    domain_totals: Dict[str, float] = {}
    for concept, score in evidence.concept_scores.items():
        domain = _FLAT_TAXONOMY[concept]["domain"]
        domain_totals[domain] = domain_totals.get(domain, 0.0) + score
    return max(domain_totals, key=domain_totals.get) if domain_totals else "General"

def _classify_metric(evidence: BusinessConceptEvidence, profile: ColumnProfile) -> str:
    if evidence.candidate_concepts:
        primary = max(evidence.candidate_concepts, key=lambda c: evidence.concept_scores.get(c, 0.0))
        metric = _FLAT_TAXONOMY[primary].get("metric")
        if metric:
            return metric
    vt = profile.value_type
    if vt == "numeric":
        if any(u.lower() in {"usd", "inr", "eur", "gbp", "rs", "$"} for u in profile.units):
            return "Money"
        if any(u.lower() in {"%", "percent", "pct"} for u in profile.units):
            return "Percentage"
        return "Count"
    if vt == "boolean":
        return "Boolean"
    if vt == "datetime":
        return "Timestamp"
    if vt == "text":
        return "Text"
    return "Category"

def _classify_customer_dimension(evidence: BusinessConceptEvidence) -> str:
    dim_totals: Dict[str, float] = {}
    for concept, score in evidence.concept_scores.items():
        dims = _FLAT_TAXONOMY[concept].get("dimensions", [])
        for d in dims:
            dim_totals[d] = dim_totals.get(d, 0.0) + score
    return max(dim_totals, key=dim_totals.get) if dim_totals else "General"

# ------------------------------------------------------------
# Confidence engine -- deterministic with ambiguity penalty
# ------------------------------------------------------------
def _estimate_confidence(evidence: BusinessConceptEvidence, primary_concept: Optional[str]) -> float:
    if not primary_concept or primary_concept == "GenericConcept":
        return 0.0
    base = evidence.concept_scores.get(primary_concept, 0.0)
    ranked_scores = sorted(evidence.concept_scores.values(), reverse=True)
    margin = ranked_scores[0] - ranked_scores[1] if len(ranked_scores) > 1 else ranked_scores[0]
    dominance_boost = 0.10 if margin > 0.15 else (0.05 if margin > 0.08 else 0.0)
    keyword_hits = len(evidence.matched_keywords.get(primary_concept, []))
    keyword_boost = min(0.10, 0.04 * keyword_hits)
    unrelated = sum(
        1 for concept in evidence.candidate_concepts
        if concept != primary_concept and not _ontology_related(primary_concept, concept)
    )
    related = max(0, len(evidence.candidate_concepts) - 1 - unrelated)
    ambiguity_penalty = _WEIGHT_AMBIGUITY * (unrelated + 0.25 * related) / max(1, len(evidence.candidate_concepts))
    conf = base + dominance_boost + keyword_boost + ambiguity_penalty
    return max(0.0, min(1.0, conf))

def _estimate_context_confidence(evidence: BusinessConceptEvidence, primary_concept: Optional[str], fingerprint: Optional[DatasetFingerprint]) -> float:
    """Enhanced confidence that incorporates context-based score improvements."""
    base_conf = _estimate_confidence(evidence, primary_concept)
    if fingerprint is None or primary_concept is None:
        return base_conf
    meta = _FLAT_TAXONOMY.get(primary_concept, {})
    # Context boosts confidence if the primary concept aligns with dataset profile
    context_boost = 0.0
    if meta:
        domain = meta.get("domain", "General")
        if domain == fingerprint.dominant_domain:
            context_boost += 0.05
        family = _concept_to_family(primary_concept)
        if family == fingerprint.dominant_family:
            context_boost += 0.03
        if not fingerprint.is_outlier_family(primary_concept):
            context_boost += 0.02
    return max(0.0, min(1.0, base_conf + context_boost))


# ------------------------------------------------------------
# Public dataclass -- contract unchanged
# ------------------------------------------------------------
@dataclass(frozen=True)
class BusinessMeaning:
    """Immutable representation of the business interpretation of a column.

    All fields are derived deterministically from the supplied ``ColumnProfile``.
    """
    primary_business_concept: str
    secondary_concepts: List[str]
    domain: str
    metric_type: str
    customer_dimension: str
    business_category: str
    business_tags: List[str]
    confidence: float
    reasoning: str
    supporting_features: Dict[str, Any]
    semantic_confidence: SemanticConfidence | None = None

# ------------------------------------------------------------
# Builder -- assembles final BusinessMeaning object
# ------------------------------------------------------------
def _build_business_meaning(
    profile: ColumnProfile,
    evidence: BusinessConceptEvidence,
    domain: str,
    metric: str,
    dimension: str,
) -> BusinessMeaning:
    primary = (
        max(evidence.candidate_concepts, key=lambda c: evidence.concept_scores.get(c, 0.0))
        if evidence.candidate_concepts else "GenericConcept"
    )
    secondary = sorted(
        [c for c in evidence.candidate_concepts if c != primary],
        key=lambda c: evidence.concept_scores.get(c, 0.0),
        reverse=True,
    )
    business_category = domain
    tags = list(
        dict.fromkeys(
            _FLAT_TAXONOMY.get(primary, {}).get("business_tags", [])
            + sum((_FLAT_TAXONOMY.get(sec, {}).get("business_tags", []) for sec in secondary), [])
        )
    )
    confidence = _estimate_confidence(evidence, primary)
    kw = ", ".join(evidence.matched_keywords.get(primary, []))
    reasoning_text = (
        f"Primary concept '{primary}' (Domain: {domain}) identified using keywords [{kw}]. "
        f"Metric inferred as '{metric}' and customer dimension as '{dimension}'."
    )
    supporting = {
        "tokens": profile.tokens,
        "units": profile.units,
        "temporal_indicators": profile.temporal_indicators,
        "financial_indicators": profile.financial_indicators,
        "behavioral_indicators": profile.behavioral_indicators,
        "statistical_profile": profile.statistical_profile,
        "detected_features": profile.detected_features,
    }
    return BusinessMeaning(
        primary_business_concept=primary,
        secondary_concepts=secondary,
        domain=domain,
        metric_type=metric,
        customer_dimension=dimension,
        business_category=business_category,
        business_tags=tags,
        confidence=confidence,
        reasoning=reasoning_text,
        supporting_features=supporting,
    )


def _build_business_meaning_with_context(
    profile: ColumnProfile,
    evidence: BusinessConceptEvidence,
    domain: str,
    metric: str,
    dimension: str,
    fingerprint: Optional[DatasetFingerprint],
) -> BusinessMeaning:
    """Build BusinessMeaning with context-aware confidence and reasoning."""
    primary = (
        max(evidence.candidate_concepts, key=lambda c: evidence.concept_scores.get(c, 0.0))
        if evidence.candidate_concepts else "GenericConcept"
    )
    secondary = sorted(
        [c for c in evidence.candidate_concepts if c != primary],
        key=lambda c: evidence.concept_scores.get(c, 0.0),
        reverse=True,
    )
    business_category = domain
    tags = list(
        dict.fromkeys(
            _FLAT_TAXONOMY.get(primary, {}).get("business_tags", [])
            + sum((_FLAT_TAXONOMY.get(sec, {}).get("business_tags", []) for sec in secondary), [])
        )
    )
    confidence = _estimate_context_confidence(evidence, primary, fingerprint)
    kw = ", ".join(evidence.matched_keywords.get(primary, []))
    context_parts: List[str] = []
    if fingerprint is not None and fingerprint.total_columns > 0:
        context_parts.append(f"Dataset sector detected as '{fingerprint.dominant_sector}' (confidence={fingerprint.sector_confidence:.2f})")
        context_parts.append(f"Dataset dominant ontology family: '{fingerprint.dominant_family}'")
        context_parts.append(f"Dataset dominant domain: '{fingerprint.dominant_domain}'")
        context_parts.append(f"Dataset concept families: {dict(fingerprint.family_distribution)}")
    reasoning_text = (
        f"Primary concept '{primary}' (Domain: {domain}) identified using keywords [{kw}]. "
        f"Metric inferred as '{metric}' and customer dimension as '{dimension}'. "
        + (" | ".join(context_parts) if context_parts else "No dataset context available.")
    )
    supporting = {
        "tokens": profile.tokens,
        "units": profile.units,
        "temporal_indicators": profile.temporal_indicators,
        "financial_indicators": profile.financial_indicators,
        "behavioral_indicators": profile.behavioral_indicators,
        "statistical_profile": profile.statistical_profile,
        "detected_features": profile.detected_features,
    }
    if fingerprint is not None:
        supporting["dataset_fingerprint"] = {
            "dominant_sector": fingerprint.dominant_sector,
            "sector_confidence": fingerprint.sector_confidence,
            "dominant_family": fingerprint.dominant_family,
            "dominant_domain": fingerprint.dominant_domain,
            "family_distribution": fingerprint.family_distribution,
        }
    return BusinessMeaning(
        primary_business_concept=primary,
        secondary_concepts=secondary,
        domain=domain,
        metric_type=metric,
        customer_dimension=dimension,
        business_category=business_category,
        business_tags=tags,
        confidence=confidence,
        reasoning=reasoning_text,
        supporting_features=supporting,
    )


# ------------------------------------------------------------
# Public API -- unchanged signature
# ------------------------------------------------------------
def infer_business_meaning(profile: ColumnProfile) -> BusinessMeaning:
    """Infer a deterministic ``BusinessMeaning`` from a ``ColumnProfile`` using a layered reasoning pipeline.

    When called standalone (without dataset context), this uses the original
    keyword + metadata scoring without context-aware disambiguation.
    """
    pack = match_knowledge_pack(profile.raw_column)
    if pack is not None:
        confidence = from_pack_match(
            match_type=pack["match_type"],
            domain_match=True,
            canonical_available=bool(pack.get("canonical")),
            relationship_consistent=bool(pack.get("relationship_consistent")),
            alias=pack["key"],
        )
        return BusinessMeaning(
            primary_business_concept=pack["concept"], secondary_concepts=[],
            domain=pack["domain"], metric_type=pack["metric"],
            customer_dimension=pack["dimension"], business_category=pack["domain"],
            business_tags=[pack["canonical"].lower(), pack["domain"].lower()],
            confidence=confidence.score,
            reasoning=f"Sector knowledge pack resolved '{profile.raw_column}' as '{pack['concept']}'. {confidence.reason}",
            supporting_features={"knowledge_pack": pack["key"], "canonical": pack["canonical"],
                                 "profile": profile.statistical_profile},
            semantic_confidence=confidence,
        )
    evidence = _extract_concept_evidence(profile)
    domain = _classify_domain(evidence)
    metric = _classify_metric(evidence, profile)
    dimension = _classify_customer_dimension(evidence)
    return _build_business_meaning(profile, evidence, domain, metric, dimension)


def infer_business_meanings(profiles: List[ColumnProfile]) -> List[BusinessMeaning]:
    """Infer ``BusinessMeaning`` for every column in a dataset using context-aware disambiguation.

    Two-pass architecture:

    Pass 1: Compute preliminary concepts for every column independently,
            then build a dataset fingerprint (sector, ontology families, domains).

    Pass 2: Re-score every candidate for every column using context-aware
            scoring: sector prior + dataset context + ontology consistency + outlier penalty.

    This produces more semantically coherent results than independent inference
    because it resolves ambiguities using the dataset's overall semantic profile.
    """
    if not profiles:
        return []

    # For profiles that match a knowledge pack, resolve immediately and exclude
    # from context-aware processing (knowledge packs are authoritative).
    pack_meanings: List[Tuple[int, BusinessMeaning]] = []
    remaining_indices: List[int] = []
    remaining_profiles: List[ColumnProfile] = []
    for idx, profile in enumerate(profiles):
        pack = match_knowledge_pack(profile.raw_column)
        if pack is not None:
            confidence = from_pack_match(
                match_type=pack["match_type"],
                domain_match=True,
                canonical_available=bool(pack.get("canonical")),
                relationship_consistent=bool(pack.get("relationship_consistent")),
                alias=pack["key"],
            )
            meaning = BusinessMeaning(
                primary_business_concept=pack["concept"], secondary_concepts=[],
                domain=pack["domain"], metric_type=pack["metric"],
                customer_dimension=pack["dimension"], business_category=pack["domain"],
                business_tags=[pack["canonical"].lower(), pack["domain"].lower()],
                confidence=confidence.score,
                reasoning=f"Sector knowledge pack resolved '{profile.raw_column}' as '{pack['concept']}'. {confidence.reason}",
                supporting_features={"knowledge_pack": pack["key"], "canonical": pack["canonical"],
                                     "profile": profile.statistical_profile},
                semantic_confidence=confidence,
            )
            pack_meanings.append((idx, meaning))
        else:
            remaining_indices.append(idx)
            remaining_profiles.append(profile)

    if not remaining_profiles:
        # All resolved via knowledge packs -- return in original order
        all_meanings = [m for _, m in sorted(pack_meanings, key=lambda x: x[0])]
        return all_meanings

    # ---- Pass 1: Preliminary (context-free) evidence for remaining columns ----
    preliminary: List[Tuple[ColumnProfile, Dict, BusinessConceptEvidence]] = []
    for profile in remaining_profiles:
        evidence = _extract_concept_evidence(profile)
        domain = _classify_domain(evidence)
        metric = _classify_metric(evidence, profile)
        dimension = _classify_customer_dimension(evidence)
        preliminary.append((profile, {"domain": domain, "metric": metric, "dimension": dimension}, evidence))

    # Build dataset fingerprint from preliminary results
    fingerprint = _compute_dataset_fingerprint(preliminary)

    # ---- Pass 2: Context-aware re-scoring ----
    context_meanings: List[Tuple[int, BusinessMeaning]] = []
    for idx_offset, (profile, base_info, _) in enumerate(preliminary):
        original_idx = remaining_indices[idx_offset]
        evidence = _extract_concept_evidence_with_context(profile, fingerprint)
        domain = _classify_domain(evidence)
        metric = _classify_metric(evidence, profile)
        dimension = _classify_customer_dimension(evidence)
        meaning = _build_business_meaning_with_context(profile, evidence, domain, metric, dimension, fingerprint)
        context_meanings.append((original_idx, meaning))

    # Merge knowledge pack results + context-aware results in original order
    all_results: List[Tuple[int, BusinessMeaning]] = pack_meanings + context_meanings
    all_results.sort(key=lambda x: x[0])
    return [m for _, m in all_results]

