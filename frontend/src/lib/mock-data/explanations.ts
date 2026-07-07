import { PredictionExplanation } from "@/lib/types";

export const predictionExplanations: PredictionExplanation[] = [
  {
    recordId: "pred-1000",
    customerId: "TEL-88213",
    sector: "telecom",
    churnProbability: 0.87,
    narrative:
      "This customer shows a high churn risk driven primarily by a month-to-month contract combined with short tenure and elevated monthly charges. Low engagement with add-on services further reduces switching cost.",
    topContributions: [
      { feature: "Contract_Month-to-month", contribution: 0.31, direction: "increases_risk" },
      { feature: "tenure", contribution: 0.24, direction: "increases_risk" },
      { feature: "MonthlyCharges", contribution: 0.18, direction: "increases_risk" },
      { feature: "TechSupport_No", contribution: 0.11, direction: "increases_risk" },
      { feature: "PaperlessBilling", contribution: 0.06, direction: "decreases_risk" },
    ],
    concepts: [
      { name: "RECURRING_COMMITMENT", confidence: 100, reconstructable: true },
      { name: "CUSTOMER_LOYALTY", confidence: 100, reconstructable: true },
      { name: "SUPPORT_FRICTION", confidence: 30, reconstructable: true },
      { name: "ENGAGEMENT_LEVEL", confidence: 0, reconstructable: false },
      { name: "SATISFACTION_SIGNAL", confidence: 0, reconstructable: false },
    ],
  },
  {
    recordId: "pred-1004",
    customerId: "BNK-40021",
    sector: "banking",
    churnProbability: 0.71,
    narrative:
      "Declining account balance trend combined with reduced product holding signals disengagement. The customer has not adopted digital banking features in the last two quarters.",
    topContributions: [
      { feature: "Balance_Trend_90d", contribution: 0.27, direction: "increases_risk" },
      { feature: "NumOfProducts", contribution: 0.22, direction: "increases_risk" },
      { feature: "IsActiveMember", contribution: 0.19, direction: "increases_risk" },
      { feature: "CreditScore", contribution: 0.08, direction: "decreases_risk" },
      { feature: "Tenure_Years", contribution: 0.05, direction: "decreases_risk" },
    ],
    concepts: [
      { name: "RECURRING_COMMITMENT", confidence: 92, reconstructable: true },
      { name: "CUSTOMER_LOYALTY", confidence: 88, reconstructable: true },
      { name: "ENGAGEMENT_LEVEL", confidence: 74, reconstructable: true },
      { name: "SUPPORT_FRICTION", confidence: 20, reconstructable: false },
      { name: "SATISFACTION_SIGNAL", confidence: 15, reconstructable: false },
    ],
  },
  {
    recordId: "pred-1007",
    customerId: "HLT-19045",
    sector: "healthcare",
    churnProbability: 0.58,
    narrative:
      "Missed appointment frequency and a lapse in recurring prescription refills are the leading indicators for this patient's disengagement risk, partially offset by long overall tenure with the provider network.",
    topContributions: [
      { feature: "Missed_Appointments_6mo", contribution: 0.29, direction: "increases_risk" },
      { feature: "Refill_Lapse_Flag", contribution: 0.21, direction: "increases_risk" },
      { feature: "Provider_Tenure_Years", contribution: 0.14, direction: "decreases_risk" },
      { feature: "Support_Contacts", contribution: 0.09, direction: "increases_risk" },
    ],
    concepts: [
      { name: "CUSTOMER_LOYALTY", confidence: 81, reconstructable: true },
      { name: "SUPPORT_FRICTION", confidence: 55, reconstructable: true },
      { name: "ENGAGEMENT_LEVEL", confidence: 40, reconstructable: true },
      { name: "RECURRING_COMMITMENT", confidence: 12, reconstructable: false },
      { name: "SATISFACTION_SIGNAL", confidence: 8, reconstructable: false },
    ],
  },
];
