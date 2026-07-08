"use client";

import { MetricCard } from "@/components/shared/metric-card";
import { SectionCard } from "@/components/shared/section-card";
import { StageStatusBadge } from "@/components/shared/status-badge";
import { PipelineFlow } from "@/components/pipeline/pipeline-flow";
import { PredictionsTable } from "@/components/predictions/predictions-table";
import { ReportExplorer } from "@/components/reports/report-explorer";
import { RoutingDecisionsTable } from "@/components/decision-intelligence/routing-decisions-table";
import { ConceptConfidenceRadar } from "@/components/charts/concept-confidence-radar";
import { Badge } from "@/components/ui/badge";
import { sectorLabel } from "@/lib/constants/sectors";
import { mapCanonicalPipeline } from "@/lib/api/live-transform";
import { conceptConfidence, predictions, reportCategories, reportContent, reportItems, routingDecisions } from "@/lib/api/view-models";
import type { WorkspaceSection } from "@/lib/navigation";
import {
  Clock, Gauge, ShieldCheck, Sparkles, BrainCircuit, Workflow,
} from "lucide-react";

type WorkspaceData = ReturnType<typeof import("@/lib/hooks/use-analysis-workspace").useAnalysisWorkspace>;

function pct(v: unknown) {
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return n <= 1 ? `${(n * 100).toFixed(1)}%` : `${n.toFixed(1)}%`;
}

export function WorkspaceSectionView({
  section,
  data,
}: {
  section: WorkspaceSection;
  data: WorkspaceData;
}) {
  const { payload, predictions: rawPredictions, coverage, quality, routing, prediction, reasoning, decision, pipeline, metadata } = data;
  if (!payload) return null;

  const exec = (payload.execution || {}) as Record<string, unknown>;
  const dataset = (payload.dataset || {}) as Record<string, unknown>;
  const status = String(exec.status || "");
  const stages = mapCanonicalPipeline(
    (pipeline as Record<string, unknown> | undefined) || undefined,
    status
  );

  switch (section) {
    case "overview":
      return (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
            <MetricCard label="Status" value={status || "—"} icon={Workflow} />
            <MetricCard label="Industry" value={sectorLabel(String(dataset.sector || ""))} icon={Sparkles} />
            <MetricCard label="Coverage" value={pct(coverage?.coverage_score)} icon={Gauge} />
            <MetricCard label="Confidence" value={pct((payload.concept_confidence as Record<string, unknown> | undefined)?.overall_confidence)} icon={ShieldCheck} />
            <MetricCard label="Runtime" value={`${exec.execution_time_ms || 0} ms`} icon={Clock} />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SectionCard title="Decision Status" description="Framework decision intelligence output">
              <div className="space-y-2 text-sm">
                <p><span className="text-muted-foreground">Readiness:</span> {String(decision?.decision_readiness || "—")}</p>
                <p><span className="text-muted-foreground">Risk:</span> {String(decision?.risk_level || "—")}</p>
                <p><span className="text-muted-foreground">Action:</span> {String(decision?.recommended_action || "—")}</p>
              </div>
            </SectionCard>
            <SectionCard title="Framework Versions" description="Pipeline and module versions">
              <div className="space-y-2 text-sm">
                <p><span className="text-muted-foreground">Pipeline:</span> {String(metadata?.framework_version || exec.framework_version || "—")}</p>
                <p><span className="text-muted-foreground">Coverage:</span> {String(metadata?.coverage_version || "—")}</p>
                <p><span className="text-muted-foreground">Intelligence:</span> {String(metadata?.prediction_intelligence_version || "—")}</p>
              </div>
            </SectionCard>
          </div>
        </div>
      );

    case "pipeline":
      return (
        <SectionCard title="Execution Timeline" description="Stage-by-stage pipeline progression">
          <PipelineFlow stages={stages} />
        </SectionCard>
      );

    case "coverage":
      return (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <SectionCard title="Coverage Score" description={String(coverage?.explanation || coverage?.status || "")}>
            <div className="space-y-3">
              <p className="text-3xl font-semibold tabular-nums">{pct(coverage?.coverage_score)}</p>
              <Badge variant="outline">{String(coverage?.coverage_band || coverage?.status || "—")}</Badge>
              <div className="text-sm text-muted-foreground">
                <p className="font-medium text-foreground">Missing critical</p>
                <p>{((coverage?.missing_critical as string[]) || []).join(", ") || "None"}</p>
                <p className="mt-2 font-medium text-foreground">Semantic matches</p>
                <p>{((coverage?.semantic_matches as string[]) || []).join(", ") || "None"}</p>
                <p className="mt-2 font-medium text-foreground">Recovered</p>
                <p>{((coverage?.recovered_features as string[]) || []).join(", ") || "None"}</p>
              </div>
            </div>
          </SectionCard>
          <SectionCard title="Concept Confidence" description="Business concept reconstructability">
            <ConceptConfidenceRadar data={conceptConfidence(payload)} />
          </SectionCard>
        </div>
      );

    case "quality":
      return (
        <SectionCard title="Quality Gate" description="Validation checks and leakage detection">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 text-sm">
              <p>Overall: <StageStatusBadge status={quality?.overall_passed ? "complete" : "failed"} /></p>
              <p>Leakage detected: {quality?.leakage_detected ? "Yes" : "No"}</p>
              <p>Flagged: {((quality?.leakage_flagged as string[]) || []).join(", ") || "None"}</p>
              <p>Warnings: {((quality?.leakage_warned as string[]) || []).join(", ") || "None"}</p>
            </div>
            <div className="space-y-2 text-sm">
              <p className="font-medium">Failed columns</p>
              <p>{((quality?.failed_columns as string[]) || []).join(", ") || "None"}</p>
            </div>
          </div>
        </SectionCard>
      );

    case "routing":
      return (
        <SectionCard title="Routing Decision" description={String(routing?.routing_reason || "")}>
          <RoutingDecisionsTable data={routingDecisions(payload)} />
        </SectionCard>
      );

    case "prediction":
      return (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricCard label="Records" value={String(prediction?.rows || rawPredictions.length || 0)} icon={Sparkles} />
            <MetricCard label="Churners" value={String(prediction?.predicted_churners || 0)} icon={BrainCircuit} />
            <MetricCard label="Avg Probability" value={pct(prediction?.average_probability)} icon={Gauge} />
            <MetricCard label="Model" value={String(prediction?.prediction_model || routing?.selected_model || "—")} icon={Workflow} />
          </div>
          <SectionCard title="Scored Records" description="Per-row predictions from framework output">
            <PredictionsTable data={predictions(payload, rawPredictions)} />
          </SectionCard>
        </div>
      );

    case "reasoning":
      return (
        <SectionCard title="Business Reasoning" description="Prediction explanation narrative">
          <div className="space-y-3 text-sm">
            <p className="text-base font-semibold">{String(reasoning?.headline || "—")}</p>
            <p>{String(reasoning?.reason_text || "—")}</p>
            <p className="text-muted-foreground">{String(reasoning?.recommendation_text || "—")}</p>
            <div className="flex flex-wrap gap-2">
              {((reasoning?.dominant_findings as string[]) || []).map((f) => (
                <Badge key={f} variant="secondary">{f}</Badge>
              ))}
            </div>
          </div>
        </SectionCard>
      );

    case "decision":
      return (
        <SectionCard title="Decision Intelligence" description="Recommended action and evidence">
          <div className="grid gap-4 sm:grid-cols-2 text-sm">
            <div className="space-y-2">
              <p>Confidence: {pct(decision?.overall_confidence)}</p>
              <p>Business: {pct(decision?.business_confidence)}</p>
              <p>Technical: {pct(decision?.technical_confidence)}</p>
              <p>Evidence: {pct(decision?.evidence_strength)}</p>
            </div>
            <div className="space-y-2">
              <p className="font-medium">{String(decision?.recommended_action || "—")}</p>
              <ul className="list-disc pl-4 text-muted-foreground">
                {((decision?.warnings as string[]) || []).map((w) => <li key={w}>{w}</li>)}
              </ul>
            </div>
          </div>
        </SectionCard>
      );

    case "reports":
      return (
        <SectionCard title="Reports" description="Executive, technical, and audit reports" contentClassName="p-0">
          <div className="p-5">
            <ReportExplorer
              categories={reportCategories}
              reports={reportItems(payload, data.reports)}
              getContent={(category) => reportContent(payload, category)}
            />
          </div>
        </SectionCard>
      );

    default:
      return null;
  }
}
