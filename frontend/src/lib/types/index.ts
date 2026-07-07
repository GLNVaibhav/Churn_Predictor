// Shared domain types mirroring the eventual FastAPI response schema.
// The frontend is intentionally decoupled from the Python backend for
// Phase 1 — these interfaces are the "contract" that lib/api/client.ts
// fulfils with mock data today, and a real FastAPI service will fulfil
// later without any UI changes.

export type Sector = "telecom" | "banking" | "healthcare" | "ecommerce";

export type RoutingTier = "Green" | "Yellow" | "Red";

export type SelectedModel =
  | "FULL_SECTOR_MODEL"
  | "UNIVERSAL_MODEL"
  | "CORE_MODEL"
  | "CRITICAL_UNRELIABLE";

export type StageStatus = "complete" | "running" | "pending" | "warning" | "failed";

export interface DashboardStat {
  id: string;
  label: string;
  value: string;
  delta?: string;
  deltaDirection?: "up" | "down" | "flat";
  description?: string;
}

export interface SectorHealth {
  sector: Sector;
  label: string;
  churnRate: number;
  totalRecords: number;
  avgConceptConfidence: number;
  status: StageStatus;
  lastRunAt: string;
}

export interface ChurnTrendPoint {
  date: string;
  telecom: number;
  banking: number;
  healthcare: number;
  ecommerce: number;
}

export interface RecentRun {
  id: string;
  sector: Sector;
  mode: "Sector" | "Universal" | "Auto";
  routingTier: RoutingTier;
  recordCount: number;
  churnDetected: number;
  submittedAt: string;
  status: StageStatus;
}

export interface UploadedDatasetPreview {
  fileName: string;
  rowCount: number;
  columnCount: number;
  detectedSector: Sector;
  detectionConfidence: number;
  columns: {
    name: string;
    inferredType: "numeric" | "categorical" | "boolean" | "text" | "date";
    nullPercentage: number;
    sampleValues: string[];
  }[];
}

export interface PipelineStageMetric {
  label: string;
  value: string;
}

export interface PipelineStage {
  id: string;
  order: number;
  name: string;
  shortLabel: string;
  description: string;
  status: StageStatus;
  durationMs: number;
  metrics: PipelineStageMetric[];
  detail: string;
  backendModule: string;
  inputSample: string;
  outputSample: string;
  futureEndpoint: string;
  notes: string;
}

export interface PredictionRecord {
  id: string;
  customerId: string;
  sector: Sector;
  churnProbability: number;
  riskTier: "Low" | "Medium" | "High" | "Critical";
  routingTier: RoutingTier;
  selectedModel: SelectedModel;
  predictedAt: string;
  coverageScore: number;
  conceptConfidenceScore: number;
  decision: "Approved" | "Escalate" | "Refused";
  businessExplanation: string;
  supportingEvidence: string[];
  warnings: string[];
  recommendedAction: string;
}

export interface FeatureContribution {
  feature: string;
  contribution: number;
  direction: "increases_risk" | "decreases_risk";
}

export interface PredictionExplanation {
  recordId: string;
  customerId: string;
  sector: Sector;
  churnProbability: number;
  narrative: string;
  topContributions: FeatureContribution[];
  concepts: {
    name: string;
    confidence: number;
    reconstructable: boolean;
  }[];
}

export interface ConceptConfidenceEntry {
  concept: string;
  confidence: number;
  reconstructable: boolean;
  source: string;
}

export interface RoutingDecisionSummary {
  sector: Sector;
  tier: RoutingTier;
  selectedModel: SelectedModel;
  coverageScore: number;
  qualityScore: number;
  conceptConfidence: number;
  reason: string;
  timestamp: string;
}

export interface ReportItem {
  id: string;
  title: string;
  sector: Sector;
  type: "Execution Summary" | "Prediction Explanation" | "Business Reasoning" | "Drift Monitoring";
  generatedAt: string;
  sizeKb: number;
}

export interface SectorConfigSetting {
  sector: Sector;
  targetCol: string;
  modelPath: string;
  trained: boolean;
  routingThresholdGreen: number;
  routingThresholdYellow: number;
}

export interface FrameworkKpi {
  id: string;
  label: string;
  value: string;
  description?: string;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
}

export type ReportCategory =
  | "Coverage Report"
  | "Quality Report"
  | "Prediction Explanation"
  | "Decision Intelligence"
  | "Execution Summary";

export interface ReportViewerContent {
  category: ReportCategory;
  headline: string;
  summary: string;
  sections: {
    heading: string;
    body: string;
    metrics?: { label: string; value: string }[];
  }[];
}
