import type {
  ConceptConfidenceEntry,
  DashboardStat,
  FrameworkKpi,
  PredictionExplanation,
  PredictionRecord,
  RecentRun,
  ReportCategory,
  ReportItem,
  ReportViewerContent,
  RoutingDecisionSummary,
  SectorHealth,
} from "@/lib/types";
import {
  mapConceptConfidence,
  mapDecisionIntelligenceReport,
  mapExecutionSummaryReport,
  mapFrameworkKpis,
  mapPredictions,
  mapPredictionExplanation,
  mapPredictionExplanationReport,
  mapQualityReport,
  mapRecentRun,
  mapRoutingDecision,
  mapCoverageReport,
  mapDashboardStats,
  toSector,
  type PipelineStatusResponse,
} from "@/lib/api/live-transform";

type Payload = Record<string, unknown>;

export function canonicalPayload(data?: { execution?: Payload } | null): Payload | null {
  return data?.execution || null;
}

export function canonicalStatus(payload?: Payload | null) {
  const nested = payload?.execution as Payload | undefined;
  return String(nested?.status || payload?.status || "");
}

export function canonicalPipelineStatus(payload?: Payload | null): PipelineStatusResponse | null {
  if (!payload) return null;
  const execution = (payload.execution || {}) as Payload;
  const dataset = (payload.dataset || {}) as Payload;
  const prediction = (payload.prediction || {}) as Payload;
  return {
    analysis_id: String(execution.execution_id || payload.execution_id || ""),
    sector: String(dataset.sector || payload.sector || ""),
    mode: String(dataset.prediction_mode || "Auto"),
    created_at: String(execution.started_at || payload.started_at || ""),
    stages: [],
    total_duration_ms: Number(execution.execution_time_ms || 0),
    has_run: Boolean(execution.execution_id || payload.execution_id),
    coverage: (payload.coverage as Payload | null) || null,
    quality: (payload.quality as Payload | null) || null,
    routing: (payload.routing as Payload | null) || null,
    prediction_count: Number(prediction.rows || 0),
    execution_summary_text: "",
  };
}

function aggregatePredictionRow(payload: Payload): Record<string, unknown>[] {
  const prediction = (payload.prediction || {}) as Payload;
  if (!prediction.rows) return [];
  const dataset = (payload.dataset || {}) as Payload;
  const routing = (payload.routing || {}) as Payload;
  return [
    {
      CustomerID: "aggregate",
      Sector: dataset.sector,
      Churn_Probability: prediction.average_probability,
      Risk_Level: Object.keys((prediction.risk_distribution || {}) as Payload)[0] || "Low",
      Coverage_Band: routing.coverage_band,
      Selected_Model: routing.selected_model,
      Prediction_Timestamp: (payload.execution as Payload | undefined)?.completed_at,
      Coverage_Score: routing.coverage_score,
      Concept_Confidence: routing.concept_confidence,
      Explanation_Business_Reason: (payload.prediction_explanation as Payload | undefined)?.reason_text,
      Explanation_Recommendation: (payload.decision as Payload | undefined)?.recommended_action,
      Predicted_Churn: Number(prediction.predicted_churners || 0) > 0 ? "Yes" : "No",
    },
  ];
}

export function predictionRows(payload?: Payload | null, endpointRows: Record<string, unknown>[] = []) {
  if (endpointRows.length) return endpointRows;
  return payload ? aggregatePredictionRow(payload) : [];
}

export function dashboardStats(payload: Payload | null, rows: Record<string, unknown>[]): DashboardStat[] {
  return mapDashboardStats(rows, payload ? canonicalPipelineStatus(payload) : null);
}

export function frameworkKpis(payload: Payload | null): FrameworkKpi[] {
  const status = payload ? canonicalPipelineStatus(payload) : null;
  return status ? mapFrameworkKpis(status) : [];
}

export function recentRun(payload: Payload | null): RecentRun[] {
  const status = payload ? canonicalPipelineStatus(payload) : null;
  return status ? [mapRecentRun(status)] : [];
}

export function sectorHealth(payload: Payload | null, rows: Record<string, unknown>[]): SectorHealth[] {
  const status = payload ? canonicalPipelineStatus(payload) : null;
  if (!status) return [];
  const stats = dashboardStats(payload, rows);
  return [
    {
      sector: toSector(status.sector),
      label: toSector(status.sector)[0].toUpperCase() + toSector(status.sector).slice(1),
      churnRate: Number(String(stats.find((s) => s.id === "avg-churn-rate")?.value || "0").replace("%", "")),
      totalRecords: status.prediction_count,
      avgConceptConfidence: Number(String(stats.find((s) => s.id === "concept-confidence")?.value || "0").replace("%", "")),
      status: canonicalStatus(payload) === "FAILED" ? "failed" : canonicalStatus(payload) === "RUNNING" ? "running" : "complete",
      lastRunAt: status.created_at || new Date().toISOString(),
    },
  ];
}

export function predictions(payload: Payload | null, rows: Record<string, unknown>[]): PredictionRecord[] {
  return mapPredictions(predictionRows(payload, rows));
}

export function explanations(payload: Payload | null, rows: Record<string, unknown>[]): PredictionExplanation[] {
  return predictionRows(payload, rows).map(mapPredictionExplanation);
}

export function routingDecisions(payload: Payload | null): RoutingDecisionSummary[] {
  const status = payload ? canonicalPipelineStatus(payload) : null;
  return status ? [mapRoutingDecision(status)] : [];
}

export function conceptConfidence(payload: Payload | null): ConceptConfidenceEntry[] {
  const status = payload ? canonicalPipelineStatus(payload) : null;
  return status ? mapConceptConfidence(status) : [];
}

export const reportCategories: { category: ReportCategory; description: string; reportCount: number; icon: "shield-check" | "gauge" | "sparkles" | "network" | "file-text" }[] = [
  { category: "Coverage Report", description: "Coverage score, band, and missing fields", reportCount: 1, icon: "shield-check" },
  { category: "Quality Report", description: "Quality Gate pass/fail output", reportCount: 1, icon: "gauge" },
  { category: "Prediction Explanation", description: "Dataset narrative and explanation summary", reportCount: 1, icon: "sparkles" },
  { category: "Decision Intelligence", description: "Decision readiness and evidence", reportCount: 1, icon: "network" },
  { category: "Execution Summary", description: "Run identity, timing, and status", reportCount: 1, icon: "file-text" },
];

export function reportItems(payload: Payload | null, backendReports: Record<string, unknown>[] = []): ReportItem[] {
  const status = payload ? canonicalPipelineStatus(payload) : null;
  const sector = toSector(status?.sector);
  const generatedAt = status?.created_at || new Date().toISOString();
  const source: Array<Record<string, unknown> & { id?: unknown; title?: unknown; category?: unknown }> = backendReports.length
    ? backendReports
    : reportCategories.map((report) => ({ ...report, id: report.category, title: report.category }));
  return source.map((report, idx) => ({
    id: String(report.category ?? report.id ?? `report-${idx}`),
    title: String(report.title ?? report.category),
    sector,
    type: idx === 0 ? "Execution Summary" : idx === 1 ? "Business Reasoning" : "Prediction Explanation",
    generatedAt,
    sizeKb: JSON.stringify(report).length / 1000,
  }));
}

export function reportContent(payload: Payload, category: ReportCategory): ReportViewerContent {
  if (category === "Coverage Report") return mapCoverageReport((payload.coverage || {}) as Payload);
  if (category === "Quality Report") return mapQualityReport((payload.quality || {}) as Payload);
  if (category === "Decision Intelligence") {
    return mapDecisionIntelligenceReport({
      ...((payload.decision || {}) as Payload),
      adaptive_business: payload.adaptive_business,
    } as Payload);
  }
  if (category === "Prediction Explanation") return mapPredictionExplanationReport((payload.prediction_explanation || {}) as Payload);
  return mapExecutionSummaryReport(canonicalPipelineStatus(payload) as PipelineStatusResponse);
}
