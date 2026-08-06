"""One-off validation script for business meaning improvements."""
import pandas as pd
from universal_churn.business_meaning import infer_business_meaning
from universal_churn.intelligence_pipeline import infer_intelligence
from universal_churn.semantic_schema import profile_column

ECOMMERCE_COLS = [
    "WishlistItems", "Returns", "Loyalty", "BrowsingTime", "FlipkartPlus",
    "HourSpendOnApp", "CashbackAmount", "Complain", "OrderCount",
    "DaySinceLastOrder", "WarehouseToHome", "PreferredPaymentMode",
    "LoyaltyScore", "CouponRewards", "ProductReturns", "NetworkBandwidth",
    "AppointmentNoShow", "AccountBalance", "MonthlySpend",
]

BEFORE_GENERIC = 5  # documented baseline on first 12 cols
BEFORE_MEAN_CONF = 0.42  # approximate from baseline run


def main():
    print("=== Business Meaning (representative columns) ===")
    generic = 0
    conf_sum = 0.0
    for col in ECOMMERCE_COLS:
        meaning = infer_business_meaning(profile_column(col))
        if meaning.primary_business_concept == "GenericConcept":
            generic += 1
        conf_sum += meaning.confidence
        print(f"  {col:25} -> {meaning.primary_business_concept:22} conf={meaning.confidence:.3f}")
    mean_conf = conf_sum / len(ECOMMERCE_COLS)
    print(f"GenericConcept: {generic}/{len(ECOMMERCE_COLS)} (before ~{BEFORE_GENERIC}/12 on core set)")
    print(f"Mean confidence: {mean_conf:.3f} (before ~{BEFORE_MEAN_CONF:.2f} on core set)")

    df = pd.DataFrame({col: [1, 2, 3] for col in ECOMMERCE_COLS})
    intel = infer_intelligence(df)
    ctx = intel.context_validation
    canon = intel.canonical_mapping
    cov = intel.coverage.summary
    print("\n=== Pipeline metrics (synthetic ecommerce mix) ===")
    g = sum(1 for m in intel.business_meanings if m.primary_business_concept == "GenericConcept")
    print(f"GenericConcept: {g}/{len(intel.business_meanings)}")
    print(f"Mean business confidence: {sum(m.confidence for m in intel.business_meanings) / len(intel.business_meanings):.3f}")
    print(f"Context agreement score: {ctx.agreement_score:.3f}")
    print(f"Canonical mapping confidence: {canon.overall_confidence:.3f}")
    print(f"Semantic coverage: {cov.semantic_coverage:.3f}")

    telecom = pd.read_csv("tests/telecom12.csv", nrows=5)
    t_intel = infer_intelligence(telecom)
    print("\n=== Telecom regression ===")
    tg = sum(1 for m in t_intel.business_meanings if m.primary_business_concept == "GenericConcept")
    print(f"GenericConcept: {tg}/{len(t_intel.business_meanings)}")
    print(f"Mean confidence: {sum(m.confidence for m in t_intel.business_meanings) / len(t_intel.business_meanings):.3f}")


if __name__ == "__main__":
    main()
