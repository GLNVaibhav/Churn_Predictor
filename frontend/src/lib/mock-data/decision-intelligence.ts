import { ConceptConfidenceEntry, RoutingDecisionSummary } from "@/lib/types";

export const routingDecisions: RoutingDecisionSummary[] = [
  {
    sector: "telecom",
    tier: "Green",
    selectedModel: "FULL_SECTOR_MODEL",
    coverageScore: 78.4,
    qualityScore: 91,
    conceptConfidence: 46,
    reason: "High feature coverage and passed quality gate — routed to the full telecom sector model.",
    timestamp: "2026-07-03T09:12:00Z",
  },
  {
    sector: "banking",
    tier: "Green",
    selectedModel: "FULL_SECTOR_MODEL",
    coverageScore: 85.1,
    qualityScore: 94,
    conceptConfidence: 79,
    reason: "Strong canonical field resolution across all required banking features.",
    timestamp: "2026-07-03T07:44:00Z",
  },
  {
    sector: "healthcare",
    tier: "Yellow",
    selectedModel: "UNIVERSAL_MODEL",
    coverageScore: 58.2,
    qualityScore: 88,
    conceptConfidence: 51,
    reason: "Partial coverage on sector-specific fields — routed to schema-agnostic universal model with a caution flag.",
    timestamp: "2026-07-02T21:05:00Z",
  },
  {
    sector: "ecommerce",
    tier: "Green",
    selectedModel: "FULL_SECTOR_MODEL",
    coverageScore: 81.7,
    qualityScore: 90,
    conceptConfidence: 68,
    reason: "Full coverage of required e-commerce behavioral fields.",
    timestamp: "2026-07-03T05:30:00Z",
  },
  {
    sector: "telecom",
    tier: "Red",
    selectedModel: "CRITICAL_UNRELIABLE",
    coverageScore: 22.9,
    qualityScore: 41,
    conceptConfidence: 18,
    reason: "Quality gate failure detected (target leakage suspected) — prediction refused.",
    timestamp: "2026-07-02T18:02:00Z",
  },
];

export const conceptConfidenceBreakdown: ConceptConfidenceEntry[] = [
  { concept: "RECURRING_COMMITMENT", confidence: 100, reconstructable: true, source: "Resolved canonical field" },
  { concept: "CUSTOMER_LOYALTY", confidence: 100, reconstructable: true, source: "Resolved canonical field" },
  { concept: "SUPPORT_FRICTION", confidence: 30, reconstructable: true, source: "Graph fallback: Support_Contacts" },
  { concept: "ENGAGEMENT_LEVEL", confidence: 0, reconstructable: false, source: "Engagement_Volume unresolved" },
  { concept: "SATISFACTION_SIGNAL", confidence: 0, reconstructable: false, source: "No documented source for sector" },
];
