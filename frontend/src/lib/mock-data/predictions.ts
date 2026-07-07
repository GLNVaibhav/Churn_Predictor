import { PredictionRecord } from "@/lib/types";

function riskTierFor(prob: number): PredictionRecord["riskTier"] {
  if (prob >= 0.75) return "Critical";
  if (prob >= 0.5) return "High";
  if (prob >= 0.25) return "Medium";
  return "Low";
}

function decisionFor(tier: PredictionRecord["routingTier"], risk: PredictionRecord["riskTier"]): PredictionRecord["decision"] {
  if (tier === "Red") return "Refused";
  if (risk === "Critical" || risk === "High") return "Escalate";
  return "Approved";
}

const rawRecords: {
  customerId: string;
  sector: PredictionRecord["sector"];
  prob: number;
  tier: PredictionRecord["routingTier"];
  model: PredictionRecord["selectedModel"];
  coverage: number;
  concept: number;
}[] = [
  { customerId: "TEL-88213", sector: "telecom", prob: 0.87, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 91, concept: 88 },
  { customerId: "TEL-88214", sector: "telecom", prob: 0.62, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 89, concept: 85 },
  { customerId: "TEL-88215", sector: "telecom", prob: 0.34, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 90, concept: 84 },
  { customerId: "TEL-88216", sector: "telecom", prob: 0.12, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 92, concept: 87 },
  { customerId: "BNK-40021", sector: "banking", prob: 0.71, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 84, concept: 79 },
  { customerId: "BNK-40022", sector: "banking", prob: 0.45, tier: "Yellow", model: "UNIVERSAL_MODEL", coverage: 61, concept: 54 },
  { customerId: "BNK-40023", sector: "banking", prob: 0.19, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 83, concept: 77 },
  { customerId: "HLT-19045", sector: "healthcare", prob: 0.58, tier: "Yellow", model: "UNIVERSAL_MODEL", coverage: 58, concept: 49 },
  { customerId: "HLT-19046", sector: "healthcare", prob: 0.27, tier: "Yellow", model: "UNIVERSAL_MODEL", coverage: 60, concept: 51 },
  { customerId: "HLT-19047", sector: "healthcare", prob: 0.09, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 88, concept: 81 },
  { customerId: "ECM-70088", sector: "ecommerce", prob: 0.93, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 94, concept: 90 },
  { customerId: "ECM-70089", sector: "ecommerce", prob: 0.66, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 90, concept: 86 },
  { customerId: "ECM-70090", sector: "ecommerce", prob: 0.41, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 89, concept: 84 },
  { customerId: "TEL-88217", sector: "telecom", prob: 0.05, tier: "Red", model: "CRITICAL_UNRELIABLE", coverage: 22, concept: 14 },
  { customerId: "BNK-40024", sector: "banking", prob: 0.81, tier: "Green", model: "FULL_SECTOR_MODEL", coverage: 86, concept: 80 },
];

const evidenceBank: Record<string, string[]> = {
  telecom: [
    "Month-to-month contract with no renewal commitment on file",
    "Tenure below sector median (18 months)",
    "Elevated monthly charges relative to plan tier",
    "No active technical support subscription",
  ],
  banking: [
    "Declining account balance trend over the last 90 days",
    "Reduced number of held products quarter-over-quarter",
    "No digital banking feature adoption in the last two quarters",
    "Below-median credit score for the retained customer segment",
  ],
  healthcare: [
    "Missed two consecutive scheduled appointments",
    "Engagement volume below the reconstructable threshold",
    "No documented satisfaction signal for this record",
    "Plan tier downgrade recorded in the last cycle",
  ],
  ecommerce: [
    "Purchase frequency dropped over the last 60 days",
    "Cart abandonment rate above sector baseline",
    "No loyalty program engagement on file",
    "Support ticket volume trending upward",
  ],
};

const warningsBank: Record<string, string[]> = {
  Green: [],
  Yellow: ["Coverage below Full Sector Model threshold — Universal Model used", "Concept confidence partially reconstructed via graph fallback"],
  Red: ["Quality Gate failed — prediction refused", "Coverage insufficient for any trained model", "Manual review required before any action is taken"],
};

const actionBank: Record<PredictionRecord["decision"], string> = {
  Approved: "No immediate action required — continue standard engagement cadence.",
  Escalate: "Route to retention specialist within 48 hours with a targeted offer.",
  Refused: "Do not act on this score. Re-collect source data and re-run the pipeline before making any decision.",
};

export const predictionRecords: PredictionRecord[] = rawRecords.map((r, i) => {
  const riskTier = riskTierFor(r.prob);
  const decision = decisionFor(r.tier, riskTier);
  return {
    id: `pred-${1000 + i}`,
    customerId: r.customerId,
    sector: r.sector,
    churnProbability: r.prob,
    riskTier,
    routingTier: r.tier,
    selectedModel: r.model,
    predictedAt: new Date(Date.UTC(2026, 6, 3, 9, 0, 0) - i * 3600 * 1000).toISOString(),
    coverageScore: r.coverage,
    conceptConfidenceScore: r.concept,
    decision,
    businessExplanation:
      r.tier === "Red"
        ? "Insufficient feature coverage and a failed Quality Gate prevented a reliable prediction for this record."
        : `This customer shows a ${riskTier.toLowerCase()} churn risk profile based on ${evidenceBank[r.sector][0].toLowerCase()} and related signals reconstructed from canonical fields.`,
    supportingEvidence: r.tier === "Red" ? ["Quality Gate blocking violation on target column integrity"] : evidenceBank[r.sector],
    warnings: warningsBank[r.tier],
    recommendedAction: actionBank[decision],
  };
});
