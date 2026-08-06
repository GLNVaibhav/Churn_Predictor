"use client";

import { useMemo, useState } from "react";
import { MetricCard } from "@/components/shared/metric-card";
import { SectionCard } from "@/components/shared/section-card";
import { StageStatusBadge } from "@/components/shared/status-badge";
import { PipelineFlow } from "@/components/pipeline/pipeline-flow";
import { PredictionsTable } from "@/components/predictions/predictions-table";
import { ReportExplorer } from "@/components/reports/report-explorer";
import { RoutingDecisionsTable } from "@/components/decision-intelligence/routing-decisions-table";
import { ConceptConfidenceRadar } from "@/components/charts/concept-confidence-radar";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { sectorLabel } from "@/lib/constants/sectors";
import { mapCanonicalPipeline } from "@/lib/api/live-transform";
import { conceptConfidence, predictions, reportCategories, reportContent, reportItems, routingDecisions } from "@/lib/api/view-models";
import type { WorkspaceSection } from "@/lib/navigation";
import {
  Clock, Gauge, ShieldCheck, Sparkles, BrainCircuit, Workflow, TerminalSquare,
  Network, GitBranch,
} from "lucide-react";

type WorkspaceData = ReturnType<typeof import("@/lib/hooks/use-analysis-workspace").useAnalysisWorkspace>;

function pct(v: unknown) {
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return n <= 1 ? `${(n * 100).toFixed(1)}%` : `${n.toFixed(1)}%`;
}

function num(v: unknown) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function comparisonRows(metrics: Record<string, unknown>, baseline: Record<string, string>) {
  const labels: Record<string, string> = {
    coverage_score: "Coverage Score",
    concept_confidence: "Concept Confidence",
    average_churn_probability: "Avg Churn Probability",
    predicted_churners: "Predicted Churners",
    rows: "Rows Analysed",
    business_context_signals: "Business Context Signals",
  };
  return Object.entries(labels).map(([key, label]) => {
    const actual = num(metrics[key]);
    const entered = baseline[key] === "" ? null : num(baseline[key]);
    const delta = actual !== null && entered !== null ? actual - entered : null;
    return { key, label, actual, entered, delta };
  });
}

export function WorkspaceSectionView({
  section,
  data,
}: {
  section: WorkspaceSection;
  data: WorkspaceData;
}) {
  const { payload, predictions: rawPredictions, coverage, quality, routing, prediction, reasoning, decision, pipeline, metadata, semanticIntelligence } = data;
  const [baseline, setBaseline] = useState<Record<string, string>>({});
  const cliOutput = (payload?.cli_output || {}) as Record<string, unknown>;
  const adaptiveBusiness = (payload?.adaptive_business || {}) as Record<string, unknown>;
  const rows = useMemo(
    () => comparisonRows((cliOutput.comparison_metrics || {}) as Record<string, unknown>, baseline),
    [cliOutput.comparison_metrics, baseline],
  );
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
            <SectionCard title="Decision Status" description="Recommended business action and readiness">
              <div className="space-y-2 text-sm">
                <p><span className="text-muted-foreground">Readiness:</span> {String(decision?.decision_readiness || "—")}</p>
                <p><span className="text-muted-foreground">Risk:</span> {String(decision?.risk_level || "—")}</p>
                <p><span className="text-muted-foreground">Action:</span> {String(decision?.recommended_action || "—")}</p>
              </div>
            </SectionCard>
            <SectionCard title="Run Information" description="Selected analysis metadata">
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
        <SectionCard title="Analysis Timeline" description="Step-by-step progress from data intake to decision support">
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

    case "semantic": {
      const semantic = (semanticIntelligence || {}) as Record<string, unknown>;
      const meanings = ((semantic.business_meanings as Record<string, unknown>[] | undefined) || []).slice(0, 24);
      const trace = ((semantic.feature_trace as Record<string, unknown>[] | undefined) || []).slice(0, 24);
      const validation = (semantic.context_validation || {}) as Record<string, unknown>;
      const graph = (semantic.semantic_graph || {}) as Record<string, unknown>;
      return (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricCard label="Domain" value={String(validation.dataset_domain || "-")} icon={Network} />
            <MetricCard label="Consensus" value={pct(validation.consensus_score)} icon={Gauge} />
            <MetricCard label="Graph Nodes" value={String(graph.node_count || 0)} icon={GitBranch} />
            <MetricCard label="Consistency" value={pct(graph.consistency_score)} icon={ShieldCheck} />
          </div>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <SectionCard title="Business Meanings" description="Column-level semantic interpretation">
              <div className="max-h-[520px] overflow-auto rounded-md border border-border">
                <div className="grid grid-cols-[1fr_1fr_90px] border-b border-border bg-muted/40 px-3 py-2 text-xs font-medium text-muted-foreground">
                  <span>Column</span><span>Concept</span><span>Confidence</span>
                </div>
                {meanings.map((item) => (
                  <div key={String(item.column)} className="grid grid-cols-[1fr_1fr_90px] gap-2 border-b border-border/60 px-3 py-2 text-xs last:border-b-0">
                    <span className="truncate font-medium">{String(item.column)}</span>
                    <span className="truncate text-muted-foreground">{String(item.primary_business_concept || "-")}</span>
                    <span className="tabular-nums">{pct(item.confidence)}</span>
                  </div>
                ))}
              </div>
            </SectionCard>
            <SectionCard title="Feature Trace" description="Source feature to canonical destination">
              <div className="max-h-[520px] overflow-auto rounded-md border border-border">
                {trace.map((item) => (
                  <div key={String(item.source_feature)} className="border-b border-border/60 px-3 py-2 text-xs last:border-b-0">
                    <p className="font-medium">{String(item.source_feature)}</p>
                    <p className="mt-1 text-muted-foreground">
                      {String(item.business_meaning || "-")} -&gt; {String(item.semantic_entity || "-")} -&gt; {String(item.canonical_destination || "-")}
                    </p>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>
        </div>
      );
    }

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
          <div className="grid gap-4 text-sm lg:grid-cols-[0.8fr_1.2fr]">
            <div className="space-y-2">
              <p>Confidence: {pct(decision?.overall_confidence)}</p>
              <p>Business: {pct(decision?.business_confidence)}</p>
              <p>Technical: {pct(decision?.technical_confidence)}</p>
              <p>Evidence: {pct(decision?.evidence_strength)}</p>
              <p>Adaptive context: {String(decision?.adaptive_context || "No business context supplied.")}</p>
            </div>
            <div className="space-y-2">
              <p className="font-medium">{String(decision?.recommended_action || "—")}</p>
              <ul className="list-disc pl-4 text-muted-foreground">
                {((decision?.warnings as string[]) || []).map((w) => <li key={w}>{w}</li>)}
              </ul>
              <div className="rounded-md border border-border bg-muted/20 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Adaptive Business Intelligence</p>
                <p className="mt-2">Impact: {String(adaptiveBusiness.overall_business_impact || "NOT_PROVIDED")}</p>
                <p>Evidence confidence: {pct(adaptiveBusiness.evidence_confidence)}</p>
                <p>Signals: {String(adaptiveBusiness.signal_count || 0)}</p>
                <p className="mt-2 text-muted-foreground">{String(adaptiveBusiness.summary || "No external business context JSON was supplied for this run.")}</p>
                <div className="mt-3 max-h-56 overflow-auto rounded-md border border-border/70 bg-background">
                  {(((adaptiveBusiness.signals as Record<string, unknown>[] | undefined) || []).slice(0, 25)).map((signal) => (
                    <div key={`${String(signal.name)}-${String(signal.impact)}`} className="border-b border-border/60 px-3 py-2 last:border-b-0">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{String(signal.name || "Signal")}</p>
                        <Badge variant="outline">{String(signal.impact || "MEDIUM")}</Badge>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{String(signal.value || "")}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </SectionCard>
      );

    case "cli":
      return (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
          <SectionCard title="Run Evidence" description="Detailed execution evidence generated for this analysis">
            <div className="rounded-md border border-slate-800 bg-slate-950 p-4">
              <div className="mb-3 flex items-center gap-2 border-b border-slate-800 pb-2 text-xs text-slate-400">
                <TerminalSquare className="h-4 w-4" />
                analysis evidence
              </div>
              <pre className="max-h-[620px] overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-100">
                {String(cliOutput.text || "Run evidence is not available for this execution.")}
              </pre>
            </div>
          </SectionCard>
          <SectionCard title="Entered Comparison" description="Enter baseline values to compare with this run">
            <div className="space-y-3">
              {rows.map((row) => (
                <div key={row.key} className="rounded-md border border-border bg-muted/20 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">{row.label}</p>
                      <p className="text-xs text-muted-foreground">
                        Current: {row.actual === null ? "n/a" : row.key.includes("probability") || row.key.includes("confidence") || row.key.includes("coverage") ? pct(row.actual) : row.actual}
                      </p>
                    </div>
                    <Input
                      value={baseline[row.key] || ""}
                      onChange={(event) => setBaseline((prev) => ({ ...prev, [row.key]: event.target.value }))}
                      placeholder="Enter value"
                      className="h-8 w-28 text-right"
                    />
                  </div>
                  <div className="mt-2 text-xs">
                    Difference:{" "}
                    <span className={row.delta === null ? "text-muted-foreground" : row.delta >= 0 ? "text-emerald-700" : "text-red-700"}>
                      {row.delta === null ? "enter baseline" : row.key.includes("probability") || row.key.includes("confidence") || row.key.includes("coverage") ? pct(row.delta) : row.delta.toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>
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
