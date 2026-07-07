import { PipelineStage } from "@/lib/types";

// Mirrors the real execution flow implemented in universal_churn/:
// preprocessing.detect_sector -> schema_resolution -> canonical_fields ->
// coverage.compute_coverage_score -> concept_confidence -> quality_gate ->
// routing.route -> sector_pipeline/universal_pipeline predict ->
// prediction_explanation -> business_reasoning / decision reporting.
export const pipelineStages: PipelineStage[] = [
  {
    id: "upload-dataset",
    order: 1,
    name: "Upload Dataset",
    shortLabel: "Upload",
    description:
      "Raw customer dataset is ingested in any schema shape (CSV/DataFrame) with no assumptions about column names.",
    status: "complete",
    durationMs: 180,
    metrics: [
      { label: "Rows ingested", value: "1,204" },
      { label: "Columns detected", value: "19" },
      { label: "Detected sector", value: "Telecom" },
    ],
    detail:
      "The framework accepts arbitrary tabular input. No canonical schema is required at this stage — sector detection and field resolution happen downstream.",
    backendModule: "ingestion/loader.py",
    inputSample: JSON.stringify(
      { source: "real_world_telecom_customers.csv", format: "csv", sizeBytes: 214880 },
      null,
      2
    ),
    outputSample: JSON.stringify(
      { rows: 1204, columns: 19, detectedSector: "telecom", detectionConfidence: 0.92 },
      null,
      2
    ),
    futureEndpoint: "POST /api/v1/datasets/upload",
    notes: "No file is persisted in Phase 1/2 — the preview panel reflects a static mock upload response.",
  },
  {
    id: "schema-intelligence",
    order: 2,
    name: "Schema Intelligence",
    shortLabel: "Schema",
    description:
      "Column names, data types, and value distributions are profiled to infer semantic meaning per field.",
    status: "complete",
    durationMs: 320,
    metrics: [
      { label: "Semantic matches", value: "14 / 19" },
      { label: "Ambiguous columns", value: "3" },
      { label: "Unresolved columns", value: "2" },
    ],
    detail:
      "Every incoming column is scored against known field signatures (name aliases, dtype, cardinality, value ranges) to propose a canonical mapping candidate.",
    backendModule: "schema_intelligence/profiler.py",
    inputSample: JSON.stringify(
      { columns: ["customerID", "tenure", "MonthlyCharges", "Contract", "..."] },
      null,
      2
    ),
    outputSample: JSON.stringify(
      {
        matches: 14,
        ambiguous: ["PaperlessBilling", "PaymentMethod", "StreamingTV"],
        unresolved: ["_internal_flag", "row_hash"],
      },
      null,
      2
    ),
    futureEndpoint: "POST /api/v1/pipeline/schema-intelligence",
    notes: "Signature matching is name/dtype/cardinality based — no LLM inference is used at this stage.",
  },
  {
    id: "canonical-field-resolution",
    order: 3,
    name: "Canonical Field Resolution",
    shortLabel: "Canonical Fields",
    description:
      "Schema Intelligence candidates are resolved into the framework's canonical field vocabulary shared across sectors.",
    status: "complete",
    durationMs: 260,
    metrics: [
      { label: "Fields resolved", value: "16" },
      { label: "Semantic recoveries", value: "2" },
      { label: "Absent fields", value: "5" },
    ],
    detail:
      "Canonical fields (e.g. tenure, MonthlyCharges) are matched literally or semantically recovered via alias graphs, independent of the sector-specific column names used at ingestion.",
    backendModule: "canonical_fields/resolver.py",
    inputSample: JSON.stringify(
      { candidates: { tenure: "tenure", charges: "MonthlyCharges", contract_type: "Contract" } },
      null,
      2
    ),
    outputSample: JSON.stringify(
      { resolved: 16, recoveredViaAlias: ["contract_type"], absent: ["loyalty_points", "nps_score"] },
      null,
      2
    ),
    futureEndpoint: "POST /api/v1/pipeline/canonical-fields",
    notes: "Alias graphs are sector-specific and versioned alongside the trained model artifacts.",
  },
  {
    id: "coverage-intelligence",
    order: 4,
    name: "Coverage Intelligence",
    shortLabel: "Coverage",
    description:
      "Measures how much of the sector's required feature surface is available in the resolved canonical fields.",
    status: "complete",
    durationMs: 140,
    metrics: [
      { label: "Coverage score", value: "78.4%" },
      { label: "Required features present", value: "16 / 21" },
      { label: "Coverage class", value: "Full" },
    ],
    detail:
      "Coverage Intelligence quantifies feature availability only — it does not decide whether a prediction is made. That decision belongs to Quality Gate and Adaptive Routing.",
    backendModule: "coverage/coverage.py",
    inputSample: JSON.stringify({ resolvedFields: 16, requiredFields: 21 }, null, 2),
    outputSample: JSON.stringify({ coverageScore: 0.784, coverageClass: "Full" }, null, 2),
    futureEndpoint: "POST /api/v1/pipeline/coverage-intelligence",
    notes: "compute_coverage_score() is a pure function — no side effects, fully deterministic given resolved fields.",
  },
  {
    id: "concept-confidence",
    order: 5,
    name: "Concept Confidence",
    shortLabel: "Concept Confidence",
    description:
      "Cross-references resolved fields against business concepts (e.g. RECURRING_COMMITMENT, CUSTOMER_LOYALTY) to score reconstructability.",
    status: "complete",
    durationMs: 210,
    metrics: [
      { label: "Overall confidence", value: "46.0%" },
      { label: "Reconstructable concepts", value: "3 / 5" },
      { label: "Graph fallback recoveries", value: "1" },
    ],
    detail:
      "Business concepts are reconstructed from canonical fields directly, or via graph fallback fields when no documented source exists for the sector.",
    backendModule: "concept_confidence/scorer.py",
    inputSample: JSON.stringify({ canonicalFields: ["tenure", "Contract", "MonthlyCharges"] }, null, 2),
    outputSample: JSON.stringify(
      {
        overallConfidence: 0.46,
        concepts: [
          { name: "RECURRING_COMMITMENT", confidence: 1.0 },
          { name: "CUSTOMER_LOYALTY", confidence: 1.0 },
          { name: "SUPPORT_FRICTION", confidence: 0.3 },
        ],
      },
      null,
      2
    ),
    futureEndpoint: "POST /api/v1/pipeline/concept-confidence",
    notes: "This is a business-concept reconstruction score, distinct from model prediction confidence.",
  },
  {
    id: "quality-gate",
    order: 6,
    name: "Quality Gate",
    shortLabel: "Quality Gate",
    description:
      "Runs leakage checks, target-column validation, and structural data-quality rules before any model is invoked.",
    status: "complete",
    durationMs: 95,
    metrics: [
      { label: "Leakage detected", value: "No" },
      { label: "Quality score", value: "0.91" },
      { label: "Blocking violations", value: "0" },
    ],
    detail:
      "The Quality Gate is a hard pass/fail check. A failure here can force a Red routing tier regardless of coverage or concept confidence.",
    backendModule: "quality_gate/gate.py",
    inputSample: JSON.stringify({ targetColumn: "Churn", coverageScore: 0.784 }, null, 2),
    outputSample: JSON.stringify({ passed: true, qualityScore: 0.91, violations: [] }, null, 2),
    futureEndpoint: "POST /api/v1/pipeline/quality-gate",
    notes: "Quality Gate failures are surfaced verbatim from the CLI — no severity is softened for the UI.",
  },
  {
    id: "adaptive-routing",
    order: 7,
    name: "Adaptive Routing",
    shortLabel: "Routing",
    description:
      "Combines Coverage, Quality, and Concept Confidence into a single routing decision: Full Sector Model, Universal Model, Core Model, or Refused.",
    status: "complete",
    durationMs: 60,
    metrics: [
      { label: "Routing tier", value: "Green" },
      { label: "Selected model", value: "Full Sector Model" },
      { label: "Routing reason", value: "High coverage + passed quality gate" },
    ],
    detail:
      "route() is called exactly once per prediction request. The CLI and all pipelines dispatch purely on the returned RoutingDecision — no ad-hoc routing logic exists elsewhere.",
    backendModule: "routing/router.py",
    inputSample: JSON.stringify(
      { coverageScore: 0.784, qualityScore: 0.91, conceptConfidence: 0.46 },
      null,
      2
    ),
    outputSample: JSON.stringify(
      { tier: "Green", selectedModel: "FULL_SECTOR_MODEL", reason: "High feature coverage and passed quality gate" },
      null,
      2
    ),
    futureEndpoint: "POST /api/v1/pipeline/adaptive-routing",
    notes: "route() is the single source of truth for model selection — no page or component should re-derive routing.",
  },
  {
    id: "prediction",
    order: 8,
    name: "Prediction",
    shortLabel: "Prediction",
    description:
      "The selected model (sector-specific or universal) scores each record and produces churn probabilities.",
    status: "complete",
    durationMs: 420,
    metrics: [
      { label: "Records scored", value: "1,204" },
      { label: "Predicted churners", value: "318" },
      { label: "Model", value: "telecom_best.pkl" },
    ],
    detail:
      "Sector models are trained per-vertical; the Universal Model provides a schema-agnostic fallback when sector-specific coverage is insufficient.",
    backendModule: "sector_pipeline/predict.py",
    inputSample: JSON.stringify({ model: "telecom_best.pkl", records: 1204 }, null, 2),
    outputSample: JSON.stringify({ scored: 1204, predictedChurners: 318, avgProbability: 0.264 }, null, 2),
    futureEndpoint: "POST /api/v1/pipeline/predict",
    notes: "Model artifacts are loaded once per run and cached in-process — never re-trained during inference.",
  },
  {
    id: "prediction-explanation",
    order: 9,
    name: "Prediction Explanation",
    shortLabel: "Explanation",
    description:
      "Attaches feature-level contribution breakdowns and natural-language narratives to each prediction — additive and non-blocking.",
    status: "complete",
    durationMs: 310,
    metrics: [
      { label: "Records explained", value: "1,204" },
      { label: "Avg. top features", value: "5" },
      { label: "Explanation coverage", value: "100%" },
    ],
    detail:
      "This layer never blocks prediction output — if explanation generation fails for a record, the base prediction is still returned untouched.",
    backendModule: "prediction_explanation/explainer.py",
    inputSample: JSON.stringify({ recordId: "TEL-88213", probability: 0.87 }, null, 2),
    outputSample: JSON.stringify(
      {
        narrative: "High churn risk driven by month-to-month contract and short tenure.",
        topFeatures: ["Contract_Month-to-month", "tenure", "MonthlyCharges"],
      },
      null,
      2
    ),
    futureEndpoint: "POST /api/v1/pipeline/explain",
    notes: "Explanations are additive-only; a failure here degrades gracefully and never blocks the base prediction.",
  },
  {
    id: "decision-intelligence",
    order: 10,
    name: "Decision Intelligence",
    shortLabel: "Decision Intelligence",
    description:
      "Synthesizes routing rationale, business concepts, and explanations into a decision-grade report for stakeholders.",
    status: "complete",
    durationMs: 190,
    metrics: [
      { label: "Reports generated", value: "1" },
      { label: "Business concepts cited", value: "3" },
      { label: "Routing tier", value: "Green" },
    ],
    detail:
      "The final stage packages the entire execution trace — coverage, quality, routing, and explanation — into a single auditable decision record.",
    backendModule: "decision_intelligence/reporter.py",
    inputSample: JSON.stringify(
      { routing: "Green", conceptsCited: 3, explanationsAttached: 1204 },
      null,
      2
    ),
    outputSample: JSON.stringify(
      { reportId: "DEC-1042", auditable: true, businessConceptsCited: ["RECURRING_COMMITMENT", "CUSTOMER_LOYALTY", "SUPPORT_FRICTION"] },
      null,
      2
    ),
    futureEndpoint: "POST /api/v1/pipeline/decision-intelligence",
    notes: "This record is the single audit trail artifact referenced by the Reports page for a given run.",
  },
];
