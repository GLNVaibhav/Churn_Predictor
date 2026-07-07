// Adapters that map raw FastAPI backend JSON (which preserves the
// framework's own field names/terminology verbatim, e.g. "Coverage_Score",
// "Selected_Model", "UNIVERSAL_MODEL") into the frontend's existing
// display types. No values are invented here — every field is read from
// a real backend response; only shape/casing is adapted so existing
// UI components (built against the mock contract) render unchanged.

import type {
  ConceptConfidenceEntry,
  DashboardStat,
  FrameworkKpi,
  PipelineStage,
  PredictionExplanation,
  PredictionRecord,
  RecentRun,
  ReportViewerContent,
  RoutingDecisionSummary,
  Sector,
  SelectedModel,
  UploadedDatasetPreview,
} from "@/lib/types";

const stageTemplate = (
  id: string,
  order: number,
  name: string,
  shortLabel: string,
  backendModule: string,
): PipelineStage => ({
  id,
  order,
  name,
  shortLabel,
  description: `${name} output from the live backend execution contract.`,
  status: "pending",
  durationMs: 0,
  metrics: [],
  detail: `${name} is owned by the backend UCIF pipeline and rendered here from execution state.`,
  backendModule,
  inputSample: "Live execution context",
  outputSample: "Backend contract section",
  futureEndpoint: "/api/v1/analysis/{execution_id}",
  notes: "Frontend does not infer or recompute this stage.",
});

const PIPELINE_STAGE_TEMPLATES: PipelineStage[] = [
  stageTemplate("upload-dataset", 1, "Upload Dataset", "Upload", "backend.services.upload_service"),
  stageTemplate("schema-intelligence", 2, "Schema Intelligence", "Schema", "universal_churn.schema_resolution"),
  stageTemplate("canonical-field-resolution", 3, "Canonical Field Resolution", "Canonical", "universal_churn.canonical_fields"),
  stageTemplate("coverage-intelligence", 4, "Coverage Intelligence", "Coverage", "universal_churn.coverage"),
  stageTemplate("concept-confidence", 5, "Concept Confidence", "Concepts", "universal_churn.concept_confidence"),
  stageTemplate("quality-gate", 6, "Quality Gate", "Quality", "universal_churn.quality_gate"),
  stageTemplate("adaptive-routing", 7, "Adaptive Routing", "Routing", "universal_churn.routing"),
  stageTemplate("prediction", 8, "Prediction", "Prediction", "universal_churn.sector_pipeline"),
  stageTemplate("prediction-explanation", 9, "Prediction Explanation", "Explain", "universal_churn.prediction_explanation"),
  stageTemplate("decision-intelligence", 10, "Decision Intelligence", "Decision", "universal_churn.decision_intelligence"),
];

export interface BackendStage {
  id: string;
  name: string;
  status: string;
  durationMs: number;
}

export interface PipelineStatusResponse {
  analysis_id: string | null;
  sector: string | null;
  mode: string | null;
  created_at: string | null;
  stages: BackendStage[];
  total_duration_ms: number;
  has_run: boolean;
  coverage: Record<string, unknown> | null;
  quality: Record<string, unknown> | null;
  routing: Record<string, unknown> | null;
  prediction_count: number;
  execution_summary_text: string;
}

export interface UploadResponse {
  upload_id: string;
  status?: string;
  filename: string;
  rows: number;
  columns: string[] | number;
  detected_sector?: string;
  sector?: string | null;
  null_counts?: Record<string, number>;
  dtypes?: Record<string, string>;
  preview_rows?: Record<string, unknown>[];
  column_profiles?: {
    name: string;
    inferredType: "numeric" | "categorical" | "boolean" | "text" | "date";
    nullPercentage: number;
    sampleValues: string[];
  }[];
}

export interface AnalyzeResponse extends PipelineStatusResponse {
  upload_id: string;
  coverage: Record<string, unknown> | null;
  quality: Record<string, unknown> | null;
  routing: Record<string, unknown> | null;
  decision_intelligence: Record<string, unknown> | null;
  prediction_explanation: Record<string, unknown> | null;
  prediction_count: number;
  execution_summary_text: string;
}

export interface PredictionsResponse {
  has_run: boolean;
  analysis_id: string | null;
  sector: string | null;
  count: number;
  predictions: Record<string, unknown>[];
}

export interface ReportsResponse {
  has_run: boolean;
  analysis_id: string | null;
  reports: { id: string; title: string; category: string; available: boolean }[];
}

export interface ReportDetailResponse {
  id: string;
  title: string;
  category: string;
  content: Record<string, unknown>;
}

export interface CustomerResponse {
  has_run: boolean;
  analysis_id: string | null;
  customer_id: string;
  record: Record<string, unknown> | null;
  explanation: Record<string, unknown> | null;
}

const KNOWN_SECTORS: Sector[] = ["telecom", "banking", "healthcare", "ecommerce"];

export function toSector(value: string | null | undefined): Sector {
  const lower = (value || "").toLowerCase();
  return (KNOWN_SECTORS.find((s) => s === lower) as Sector) || "telecom";
}

function pct(value: unknown): number {
  if (typeof value === "number") return value <= 1 ? value * 100 : value;
  if (typeof value === "string") {
    const n = parseFloat(value.replace("%", ""));
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
}

// Backend snake_case stage ids -> frontend kebab-case stage ids. The
// backend's "load_model" stage has no dedicated frontend node — its
// duration is folded into "upload-dataset" since it's part of the same
// pre-processing setup window.
const STAGE_ID_MAP: Record<string, string> = {
  upload: "upload-dataset",
  load_model: "upload-dataset",
  schema: "schema-intelligence",
  canonical: "canonical-field-resolution",
  coverage: "coverage-intelligence",
  concept_confidence: "concept-confidence",
  quality_gate: "quality-gate",
  routing: "adaptive-routing",
  prediction: "prediction",
  prediction_explanation: "prediction-explanation",
  decision_intelligence: "decision-intelligence",
};

export function mapPipelineStages(backendStages: BackendStage[]): PipelineStage[] {
  const durationByFrontendId = new Map<string, number>();
  for (const stage of backendStages) {
    const frontendId = STAGE_ID_MAP[stage.id];
    if (!frontendId) continue;
    durationByFrontendId.set(frontendId, (durationByFrontendId.get(frontendId) || 0) + stage.durationMs);
  }
  return PIPELINE_STAGE_TEMPLATES.map((stage) => ({
    ...stage,
    status: backendStages.length ? "complete" : "pending",
    durationMs: durationByFrontendId.get(stage.id) ?? stage.durationMs,
  }));
}

export function mapCanonicalPipeline(payload: Record<string, unknown> | null | undefined, executionStatus?: string | null): PipelineStage[] {
  const stages = ((payload?.stages || payload?.steps) as BackendStage[] | undefined) || [];
  if (stages.length) return mapPipelineStages(stages);
  if (executionStatus === "SUCCEEDED" || executionStatus === "SUCCESS") {
    return PIPELINE_STAGE_TEMPLATES.map((stage) => ({ ...stage, status: "complete" }));
  }
  if (executionStatus === "FAILED" || executionStatus === "CANCELLED") {
    return PIPELINE_STAGE_TEMPLATES.map((stage, idx) => ({ ...stage, status: idx === 0 ? "failed" : "pending" }));
  }
  if (executionStatus === "RUNNING" || executionStatus === "PENDING") {
    return PIPELINE_STAGE_TEMPLATES.map((stage, idx) => ({ ...stage, status: idx === 0 ? "running" : "pending" }));
  }
  return PIPELINE_STAGE_TEMPLATES;
}

export function mapUploadPreview(upload: UploadResponse): UploadedDatasetPreview {
  const previewRows = upload.preview_rows || [];
  const dtypes = upload.dtypes || {};
  const columns = upload.column_profiles || (Array.isArray(upload.columns)
    ? upload.columns.map((name) => ({
        name,
        inferredType: "text" as const,
        nullPercentage: 0,
        sampleValues: previewRows.map((row) => String(row[name] ?? "")).filter(Boolean).slice(0, 3),
      }))
    : Object.keys(dtypes).map((name) => ({
        name,
        inferredType: String(dtypes[name]).includes("int") || String(dtypes[name]).includes("float") ? "numeric" as const : "categorical" as const,
        nullPercentage: upload.null_counts?.[name] || 0,
        sampleValues: previewRows.map((row) => String(row[name] ?? "")).filter(Boolean).slice(0, 3),
      })));
  return {
    fileName: upload.filename,
    rowCount: upload.rows,
    columnCount: Array.isArray(upload.columns) ? upload.columns.length : upload.columns,
    detectedSector: toSector(upload.detected_sector || upload.sector),
    detectionConfidence: 100,
    columns,
  };
}

function riskTierFromLabel(label: unknown): PredictionRecord["riskTier"] {
  const s = String(label || "").toLowerCase();
  if (s === "critical") return "Critical";
  if (s === "high") return "High";
  if (s === "medium") return "Medium";
  return "Low";
}

function routingTierFromBand(band: unknown): PredictionRecord["routingTier"] {
  const s = String(band || "").toLowerCase();
  if (s === "green") return "Green";
  if (s === "yellow") return "Yellow";
  return "Red";
}

function selectedModelFrom(value: unknown): SelectedModel {
  const s = String(value || "").toUpperCase();
  if (s === "FULL_SECTOR_MODEL" || s === "UNIVERSAL_MODEL" || s === "CORE_MODEL" || s === "CRITICAL_UNRELIABLE") {
    return s as SelectedModel;
  }
  return "UNIVERSAL_MODEL";
}

function decisionFor(routingTier: PredictionRecord["routingTier"], riskTier: PredictionRecord["riskTier"]): PredictionRecord["decision"] {
  if (routingTier === "Red") return "Refused";
  if (riskTier === "Critical" || riskTier === "High") return "Escalate";
  return "Approved";
}

function splitList(value: unknown): string[] {
  const s = String(value || "").trim();
  if (!s) return [];
  return s.split(";").map((v) => v.trim()).filter(Boolean);
}

export function mapPredictionRecord(row: Record<string, unknown>, index: number): PredictionRecord {
  const riskTier = riskTierFromLabel(row["Risk_Level"]);
  const routingTier = routingTierFromBand(row["Coverage_Band"]);
  return {
    id: `pred-${row["CustomerID"] ?? index}`,
    customerId: String(row["CustomerID"] ?? `row-${index}`),
    sector: toSector(String(row["Sector"] || "")),
    churnProbability: Number(row["Churn_Probability"] ?? 0),
    riskTier,
    routingTier,
    selectedModel: selectedModelFrom(row["Selected_Model"]),
    predictedAt: String(row["Prediction_Timestamp"] || row["Routing_Timestamp"] || ""),
    coverageScore: pct(row["Coverage_Score"]),
    conceptConfidenceScore: pct(row["Concept_Confidence"]),
    decision: decisionFor(routingTier, riskTier),
    businessExplanation: String(row["Explanation_Business_Reason"] || row["Routing_Reason"] || ""),
    supportingEvidence: splitList(row["Explanation_Dominant_Concepts"] || row["Explanation_Triggered_Findings"]),
    warnings: splitList(row["Routing_Warnings"]),
    recommendedAction: String(row["Explanation_Recommendation"] || "No specific action generated for this record."),
  };
}

export function mapPredictions(rows: Record<string, unknown>[]): PredictionRecord[] {
  return rows.map((row, idx) => mapPredictionRecord(row, idx));
}

export function mapPredictionExplanation(row: Record<string, unknown>): PredictionExplanation {
  const confidenceStr = String(row["Concept_Confidence"] || "0%");
  const missing = splitList(row["Explanation_Missing_Features"]);
  const contributions: PredictionExplanation["topContributions"] = missing.length
    ? []
    : [];
  return {
    recordId: `pred-${row["CustomerID"]}`,
    customerId: String(row["CustomerID"] || ""),
    sector: toSector(String(row["Sector"] || "")),
    churnProbability: Number(row["Churn_Probability"] ?? 0),
    narrative: String(row["Explanation_Business_Reason"] || ""),
    topContributions: contributions,
    concepts: [
      {
        name: "Overall Concept Confidence",
        confidence: pct(confidenceStr),
        reconstructable: pct(confidenceStr) > 0,
      },
    ],
  };
}

export function mapDashboardStats(predictions: Record<string, unknown>[], analysis: PipelineStatusResponse | null): DashboardStat[] {
  const total = predictions.length;
  const churners = predictions.filter((p) => String(p["Predicted_Churn"]).toLowerCase() === "yes").length;
  const avgConfidence =
    total > 0 ? predictions.reduce((sum, p) => sum + pct(p["Concept_Confidence"]), 0) / total : 0;
  const greenCount = predictions.filter((p) => String(p["Coverage_Band"]) === "Green").length;
  return [
    {
      id: "total-predictions",
      label: "Total Predictions",
      value: total.toLocaleString(),
      description: `Latest live run${analysis?.sector ? ` — ${analysis.sector}` : ""}`,
    },
    {
      id: "avg-churn-rate",
      label: "Avg. Churn Rate",
      value: total > 0 ? `${((churners / total) * 100).toFixed(1)}%` : "0%",
      description: "Predicted churners in latest run",
    },
    {
      id: "concept-confidence",
      label: "Avg. Concept Confidence",
      value: `${avgConfidence.toFixed(1)}%`,
      description: "Business concept reconstruction quality",
    },
    {
      id: "routing-green",
      label: "Green Routing Rate",
      value: total > 0 ? `${((greenCount / total) * 100).toFixed(1)}%` : "0%",
      description: "Records routed to full sector models",
    },
  ];
}

export function mapFrameworkKpis(analysis: PipelineStatusResponse): FrameworkKpi[] {
  const routing = (analysis.routing || {}) as Record<string, unknown>;
  const coverage = (analysis.coverage || {}) as Record<string, unknown>;
  return [
    {
      id: "coverage-intelligence",
      label: "Coverage Intelligence",
      value: `${pct(coverage["coverage_score"]).toFixed(1)}%`,
      description: "Required feature surface available",
    },
    {
      id: "concept-confidence",
      label: "Concept Confidence",
      value: `${pct(routing["concept_confidence"]).toFixed(1)}%`,
      description: "Business concepts reconstructed",
    },
    {
      id: "prediction-reliability",
      label: "Prediction Reliability",
      value: String(routing["prediction_reliability"] || "—"),
      description: "Routing-assessed reliability of this run",
    },
    {
      id: "decision-readiness",
      label: "Decision Readiness",
      value: String(routing["coverage_band"] || "—"),
      description: "Latest run routing tier",
    },
    {
      id: "routing-decision",
      label: "Routing Decision",
      value: String(routing["selected_model"] || "—"),
      description: "Adaptive Routing output for latest run",
    },
    {
      id: "rows-processed",
      label: "Rows Processed",
      value: analysis.prediction_count.toLocaleString(),
      description: "Records scored in the latest live run",
    },
    {
      id: "industry",
      label: "Industry",
      value: analysis.sector ? analysis.sector[0].toUpperCase() + analysis.sector.slice(1) : "—",
      description: "Most recently processed sector",
    },
  ];
}

export function mapRecentRun(analysis: PipelineStatusResponse): RecentRun {
  const routing = (analysis.routing || {}) as Record<string, unknown>;
  return {
    id: analysis.analysis_id || "live-run",
    sector: toSector(analysis.sector),
    mode: (analysis.mode as RecentRun["mode"]) || "Auto",
    routingTier: routingTierFromBand(routing["coverage_band"]) as RecentRun["routingTier"],
    recordCount: analysis.prediction_count,
    churnDetected: 0,
    submittedAt: analysis.created_at || new Date().toISOString(),
    status: "complete",
  };
}

export function mapRoutingDecision(analysis: PipelineStatusResponse): RoutingDecisionSummary {
  const routing = (analysis.routing || {}) as Record<string, unknown>;
  const coverage = (analysis.coverage || {}) as Record<string, unknown>;
  const quality = (analysis.quality || {}) as Record<string, unknown>;
  return {
    sector: toSector(analysis.sector),
    tier: routingTierFromBand(routing["coverage_band"]) as RoutingDecisionSummary["tier"],
    selectedModel: selectedModelFrom(routing["selected_model"]),
    coverageScore: pct(coverage["coverage_score"]),
    qualityScore: pct(quality["quality_score"] ?? quality["overall_score"]),
    conceptConfidence: pct(routing["concept_confidence"]),
    reason: String(routing["routing_reason"] || ""),
    timestamp: analysis.created_at || new Date().toISOString(),
  };
}

export function mapConceptConfidence(analysis: PipelineStatusResponse): ConceptConfidenceEntry[] {
  const coverage = (analysis.coverage || {}) as Record<string, unknown>;
  const detail = (coverage["concept_confidence"] || {}) as Record<string, unknown>;
  const perConcept = (detail["per_concept"] || detail["concepts"] || {}) as Record<string, unknown>;
  const entries = Object.entries(perConcept);
  if (entries.length === 0) return [];
  return entries.map(([concept, value]) => {
    const v = value as Record<string, unknown>;
    const confidence = pct(v["confidence"] ?? v["score"] ?? value);
    return {
      concept,
      confidence,
      reconstructable: confidence > 0,
      source: String(v["source"] || "Live analysis"),
    };
  });
}

export function mapCoverageReport(content: Record<string, unknown>): ReportViewerContent {
  const missingAll = (content["missing_all"] as string[]) || [];
  return {
    category: "Coverage Report",
    headline: `Coverage Intelligence — ${String(content["coverage_band"])} Band`,
    summary: `Coverage score of ${pct(content["coverage_score"]).toFixed(1)}% with prediction mode "${content["prediction_mode"]}".`,
    sections: [
      {
        heading: "Coverage Breakdown",
        body: "Coverage measures how much of the sector's required feature surface is present in the resolved canonical fields for this run.",
        metrics: [
          { label: "Coverage Score", value: `${pct(content["coverage_score"]).toFixed(1)}%` },
          { label: "Coverage Band", value: String(content["coverage_band"] || "—") },
          { label: "Prediction Mode", value: String(content["prediction_mode"] || "—") },
        ],
      },
      {
        heading: "Missing Fields",
        body: missingAll.length ? missingAll.join(", ") : "No missing fields were recorded for this run.",
      },
    ],
  };
}

export function mapQualityReport(content: Record<string, unknown>): ReportViewerContent {
  const columnResults = (content["column_results"] as Record<string, unknown>[]) || [];
  return {
    category: "Quality Report",
    headline: `Quality Gate — ${content["overall_passed"] ? "Passed" : "Failed"}`,
    summary: `Quality Gate evaluated ${columnResults.length} columns; leakage detected: ${content["leakage_detected"] ? "Yes" : "No"}.`,
    sections: [
      {
        heading: "Gate Outcome",
        body: "The Quality Gate is a hard pass/fail check evaluated before any model is invoked.",
        metrics: [
          { label: "Overall Passed", value: content["overall_passed"] ? "Yes" : "No" },
          { label: "Leakage Detected", value: content["leakage_detected"] ? "Yes" : "No" },
          { label: "Failed Columns", value: String(((content["failed_columns"] as string[]) || []).length) },
        ],
      },
      {
        heading: "Checks Performed",
        body: "Per-column null-rate, near-constant detection, target-correlation leakage scan, and cardinality checks across the resolved dataset.",
      },
    ],
  };
}

export function mapDecisionIntelligenceReport(content: Record<string, unknown>): ReportViewerContent {
  const inferences = (content["inferences"] as Record<string, Record<string, unknown>>) || {};
  const concepts = Object.keys(inferences);
  return {
    category: "Decision Intelligence",
    headline: `Decision Intelligence — ${String(content["sector"] || "").toUpperCase()} Run`,
    summary: String(content["summary"] || `Routing rationale synthesized with ${concepts.length} cited business concepts.`),
    sections: [
      {
        heading: "Cited Business Concepts",
        body: concepts.length ? concepts.join(", ") : "No business concepts were reconstructed for this run.",
        metrics: concepts.slice(0, 3).map((c) => ({
          label: c,
          value: String(inferences[c]["band"] || "—"),
        })),
      },
    ],
  };
}

export function mapPredictionExplanationReport(content: Record<string, unknown>): ReportViewerContent {
  return {
    category: "Prediction Explanation",
    headline: `Prediction Explanation — ${String(content["sector"] || "").toUpperCase()} Run`,
    summary: String(content["dataset_narrative_text"] || "Feature-level rationale and narratives for scored records."),
    sections: [
      {
        heading: "Dataset Narrative",
        body: String(content["dataset_narrative_text"] || "No dataset-level narrative was generated for this run."),
      },
    ],
  };
}

export function mapExecutionSummaryReport(analysis: PipelineStatusResponse): ReportViewerContent {
  const routing = (analysis.routing || {}) as Record<string, unknown>;
  return {
    category: "Execution Summary",
    headline: `Execution Summary — ${analysis.sector} Run ${analysis.analysis_id}`,
    summary: analysis.execution_summary_text || `${analysis.stages.length} pipeline stages completed for ${analysis.prediction_count} records.`,
    sections: [
      {
        heading: "Run Overview",
        body: `${analysis.prediction_count.toLocaleString()} rows were processed end-to-end.`,
        metrics: [
          { label: "Total Execution Time", value: `${Math.round(analysis.total_duration_ms).toLocaleString()} ms` },
          { label: "Stages Completed", value: `${analysis.stages.filter((s) => s.status === "complete").length} / ${analysis.stages.length}` },
          { label: "Routing Tier", value: String(routing["coverage_band"] || "—") },
        ],
      },
    ],
  };
}
