import { ReportCategory, ReportItem, ReportViewerContent } from "@/lib/types";

export const reportItems: ReportItem[] = [
  {
    id: "rpt-2201",
    title: "Telecom Execution Summary — Jul 3, 2026",
    sector: "telecom",
    type: "Execution Summary",
    generatedAt: "2026-07-03T09:14:00Z",
    sizeKb: 128,
  },
  {
    id: "rpt-2200",
    title: "Banking Prediction Explanation Report",
    sector: "banking",
    type: "Prediction Explanation",
    generatedAt: "2026-07-03T07:46:00Z",
    sizeKb: 214,
  },
  {
    id: "rpt-2199",
    title: "Healthcare Business Reasoning Report",
    sector: "healthcare",
    type: "Business Reasoning",
    generatedAt: "2026-07-02T21:08:00Z",
    sizeKb: 96,
  },
  {
    id: "rpt-2198",
    title: "E-commerce Drift Monitoring — Weekly",
    sector: "ecommerce",
    type: "Drift Monitoring",
    generatedAt: "2026-07-03T05:32:00Z",
    sizeKb: 64,
  },
  {
    id: "rpt-2197",
    title: "Telecom Execution Summary — Jul 2, 2026",
    sector: "telecom",
    type: "Execution Summary",
    generatedAt: "2026-07-02T18:05:00Z",
    sizeKb: 112,
  },
];

export const reportCategories: {
  category: ReportCategory;
  description: string;
  reportCount: number;
  icon: "shield-check" | "gauge" | "sparkles" | "network" | "file-text";
}[] = [
  {
    category: "Coverage Report",
    description: "Feature availability against the required sector surface, per run.",
    reportCount: 12,
    icon: "gauge",
  },
  {
    category: "Quality Report",
    description: "Leakage checks, target validation, and Quality Gate outcomes.",
    reportCount: 12,
    icon: "shield-check",
  },
  {
    category: "Prediction Explanation",
    description: "Feature-level rationale and narratives for scored records.",
    reportCount: 9,
    icon: "sparkles",
  },
  {
    category: "Decision Intelligence",
    description: "Routing rationale synthesized with business concepts.",
    reportCount: 9,
    icon: "network",
  },
  {
    category: "Execution Summary",
    description: "End-to-end pipeline run summaries across all sectors.",
    reportCount: 24,
    icon: "file-text",
  },
];

export const reportViewerContent: Record<ReportCategory, ReportViewerContent> = {
  "Coverage Report": {
    category: "Coverage Report",
    headline: "Coverage Intelligence — Telecom Run TEL-run-1042",
    summary:
      "16 of 21 required sector features were present after Canonical Field Resolution, yielding a Full coverage classification.",
    sections: [
      {
        heading: "Coverage Breakdown",
        body: "Required features are drawn from the telecom sector schema definition. Absent fields degrade coverage class but do not block a prediction on their own.",
        metrics: [
          { label: "Coverage Score", value: "78.4%" },
          { label: "Required Features Present", value: "16 / 21" },
          { label: "Coverage Class", value: "Full" },
        ],
      },
      {
        heading: "Absent Fields",
        body: "loyalty_points, nps_score, and 3 additional optional fields were not present in the resolved canonical field set for this run.",
      },
    ],
  },
  "Quality Report": {
    category: "Quality Report",
    headline: "Quality Gate — Telecom Run TEL-run-1042",
    summary: "No leakage detected. Quality Gate passed with a score of 0.91 and zero blocking violations.",
    sections: [
      {
        heading: "Gate Outcome",
        body: "The Quality Gate is a hard pass/fail check evaluated before any model is invoked. This run passed cleanly.",
        metrics: [
          { label: "Leakage Detected", value: "No" },
          { label: "Quality Score", value: "0.91" },
          { label: "Blocking Violations", value: "0" },
        ],
      },
      {
        heading: "Checks Performed",
        body: "Target-column leakage scan, duplicate-record detection, structural null-rate thresholds, and canonical field type consistency.",
      },
    ],
  },
  "Prediction Explanation": {
    category: "Prediction Explanation",
    headline: "Prediction Explanation — Banking Run BNK-run-0871",
    summary: "1,204 records explained with an average of 5 top contributing features per record; 100% explanation coverage.",
    sections: [
      {
        heading: "Explanation Coverage",
        body: "Every scored record received an attached explanation. No explanation failures were recorded for this run.",
        metrics: [
          { label: "Records Explained", value: "1,204" },
          { label: "Avg. Top Features", value: "5" },
          { label: "Explanation Coverage", value: "100%" },
        ],
      },
      {
        heading: "Representative Narrative",
        body: "\"Declining account balance trend combined with reduced product holding signals disengagement. The customer has not adopted digital banking features in the last two quarters.\"",
      },
    ],
  },
  "Decision Intelligence": {
    category: "Decision Intelligence",
    headline: "Decision Intelligence — Healthcare Run HLT-run-0512",
    summary: "Routing rationale synthesized with 3 cited business concepts into a single auditable decision record.",
    sections: [
      {
        heading: "Routing Rationale",
        body: "Yellow routing tier selected due to partial coverage; the Universal Model was used as the schema-agnostic fallback.",
        metrics: [
          { label: "Routing Tier", value: "Yellow" },
          { label: "Selected Model", value: "Universal Model" },
          { label: "Concepts Cited", value: "3" },
        ],
      },
      {
        heading: "Cited Business Concepts",
        body: "RECURRING_COMMITMENT, CUSTOMER_LOYALTY, and SUPPORT_FRICTION were reconstructed and cited in this decision record.",
      },
    ],
  },
  "Execution Summary": {
    category: "Execution Summary",
    headline: "Execution Summary — Telecom Run TEL-run-1042",
    summary: "All 10 pipeline stages completed successfully in 2,185ms total execution time.",
    sections: [
      {
        heading: "Run Overview",
        body: "1,204 rows were ingested and processed end-to-end with no blocking violations across any stage.",
        metrics: [
          { label: "Total Execution Time", value: "2,185 ms" },
          { label: "Stages Completed", value: "10 / 10" },
          { label: "Routing Tier", value: "Green" },
        ],
      },
      {
        heading: "Outcome",
        body: "318 of 1,204 customers were predicted as likely to churn. All predictions carry attached explanations and a synthesized decision record.",
      },
    ],
  },
};
