// API abstraction layer.
//
// Every function first attempts to read from the live FastAPI backend
// (backend_api/) which orchestrates the real, unmodified
// `universal_churn` framework. If no analysis has run yet, or the
// backend is unreachable, it falls back to the Phase 1/2 mock data so
// the UI always renders something meaningful. No page or component
// needs to change based on which source served the data.

import {
  ChurnTrendPoint,
  DashboardStat,
  FrameworkKpi,
  PredictionExplanation,
  PredictionRecord,
  RecentRun,
  ReportCategory,
  ReportItem,
  ReportViewerContent,
  RoutingDecisionSummary,
  ConceptConfidenceEntry,
  SectorConfigSetting,
  SectorHealth,
  UploadedDatasetPreview,
  PipelineStage,
} from "@/lib/types";

import { dashboardStats, sectorHealth, churnTrend, recentRuns, frameworkKpis } from "@/lib/mock-data/dashboard";
import { pipelineStages } from "@/lib/mock-data/pipeline";
import { predictionRecords } from "@/lib/mock-data/predictions";
import { predictionExplanations } from "@/lib/mock-data/explanations";
import { routingDecisions, conceptConfidenceBreakdown } from "@/lib/mock-data/decision-intelligence";
import { reportItems, reportCategories, reportViewerContent } from "@/lib/mock-data/reports";
import { sectorConfigSettings, uploadPreview } from "@/lib/mock-data/settings";

import { backendGet } from "@/lib/api/backend";
import {
  AnalyzeResponse,
  PipelineStatusResponse,
  PredictionsResponse,
  ReportDetailResponse,
  ReportsResponse,
  mapConceptConfidence,
  mapCoverageReport,
  mapDashboardStats,
  mapDecisionIntelligenceReport,
  mapExecutionSummaryReport,
  mapFrameworkKpis,
  mapPipelineStages,
  mapPredictionExplanationReport,
  mapPredictionExplanation,
  mapPredictions,
  mapQualityReport,
  mapRecentRun,
  mapRoutingDecision,
} from "@/lib/api/live-transform";

const MOCK_LATENCY_MS = 0;

function resolveMock<T>(data: T): Promise<T> {
  if (MOCK_LATENCY_MS === 0) return Promise.resolve(data);
  return new Promise((resolve) => setTimeout(() => resolve(data), MOCK_LATENCY_MS));
}

async function getLiveAnalysis(): Promise<AnalyzeResponse | null> {
  const status = await backendGet<PipelineStatusResponse>("/pipeline");
  if (!status || !status.has_run) return null;
  return status as AnalyzeResponse;
}

async function getLivePredictionRows(): Promise<Record<string, unknown>[] | null> {
  const resp = await backendGet<PredictionsResponse>("/predictions");
  if (!resp || !resp.has_run) return null;
  return resp.predictions;
}

const REPORT_ID_BY_CATEGORY: Record<ReportCategory, string> = {
  "Coverage Report": "coverage",
  "Quality Report": "quality",
  "Prediction Explanation": "prediction_explanation",
  "Decision Intelligence": "decision_intelligence",
  "Execution Summary": "execution_summary",
};

export const api = {
  dashboard: {
    getStats: async (): Promise<DashboardStat[]> => {
      const rows = await getLivePredictionRows();
      const analysis = rows ? await getLiveAnalysis() : null;
      if (rows) return mapDashboardStats(rows, analysis);
      return resolveMock(dashboardStats);
    },
    getKpis: async (): Promise<FrameworkKpi[]> => {
      const analysis = await getLiveAnalysis();
      if (analysis) return mapFrameworkKpis(analysis);
      return resolveMock(frameworkKpis);
    },
    getSectorHealth: (): Promise<SectorHealth[]> => resolveMock(sectorHealth),
    getChurnTrend: (): Promise<ChurnTrendPoint[]> => resolveMock(churnTrend),
    getRecentRuns: async (): Promise<RecentRun[]> => {
      const analysis = await getLiveAnalysis();
      if (analysis) return [mapRecentRun(analysis), ...recentRuns];
      return resolveMock(recentRuns);
    },
  },
  upload: {
    getPreview: (): Promise<UploadedDatasetPreview> => resolveMock(uploadPreview),
  },
  pipeline: {
    getStages: async (): Promise<PipelineStage[]> => {
      const status = await backendGet<PipelineStatusResponse>("/pipeline");
      if (status && status.has_run) return mapPipelineStages(status.stages);
      return resolveMock(pipelineStages);
    },
  },
  predictions: {
    getAll: async (): Promise<PredictionRecord[]> => {
      const rows = await getLivePredictionRows();
      if (rows) return mapPredictions(rows);
      return resolveMock(predictionRecords);
    },
  },
  explanations: {
    getAll: async (): Promise<PredictionExplanation[]> => {
      const rows = await getLivePredictionRows();
      if (rows) return rows.map(mapPredictionExplanation);
      return resolveMock(predictionExplanations);
    },
  },
  decisionIntelligence: {
    getRoutingDecisions: async (): Promise<RoutingDecisionSummary[]> => {
      const analysis = await getLiveAnalysis();
      if (analysis) return [mapRoutingDecision(analysis), ...routingDecisions];
      return resolveMock(routingDecisions);
    },
    getConceptConfidence: async (): Promise<ConceptConfidenceEntry[]> => {
      const analysis = await getLiveAnalysis();
      if (analysis) {
        const live = mapConceptConfidence(analysis);
        if (live.length) return live;
      }
      return resolveMock(conceptConfidenceBreakdown);
    },
  },
  reports: {
    getAll: (): Promise<ReportItem[]> => resolveMock(reportItems),
    getCategories: () => resolveMock(reportCategories),
    getViewerContent: async (category: ReportCategory): Promise<ReportViewerContent> => {
      const reportId = REPORT_ID_BY_CATEGORY[category];
      const detail = await backendGet<ReportDetailResponse>(`/reports/${reportId}`);
      if (detail && detail.content) {
        switch (category) {
          case "Coverage Report":
            return mapCoverageReport(detail.content);
          case "Quality Report":
            return mapQualityReport(detail.content);
          case "Decision Intelligence":
            return mapDecisionIntelligenceReport(detail.content);
          case "Prediction Explanation":
            return mapPredictionExplanationReport(detail.content);
          case "Execution Summary": {
            const analysis = await getLiveAnalysis();
            if (analysis) return mapExecutionSummaryReport(analysis);
          }
        }
      }
      return resolveMock(reportViewerContent[category]);
    },
  },
  settings: {
    getSectorConfigs: (): Promise<SectorConfigSetting[]> => resolveMock(sectorConfigSettings),
  },
};
