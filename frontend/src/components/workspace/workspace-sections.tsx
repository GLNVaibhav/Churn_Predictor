"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SectionCard } from "@/components/shared/section-card";
import { DataSourceBadge } from "@/components/shared/data-source-badge";
import { ErrorBanner, LoadingState } from "@/components/shared/query-states";
import BarChart from "@/components/charts/bar-chart";
import { Bar } from "@/components/charts/bar";
import { BarXAxis } from "@/components/charts/bar-x-axis";
import { ChartTooltip } from "@/components/charts/tooltip/chart-tooltip";
import { Grid } from "@/components/charts/grid";
import type { WorkspaceSection } from "@/lib/navigation";
import { sectorLabel } from "@/lib/constants/sectors";
import { ArrowDown, ArrowUp, Download, Search } from "lucide-react";

type JsonObject = Record<string, unknown>;
type WorkspaceData = { payload: JsonObject | null; executionId: string | null };
const PAGE_SIZE = 10;

function object(value: unknown): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : null;
}

function array(value: unknown): unknown[] | null {
  return Array.isArray(value) ? value : null;
}

function populated(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as JsonObject).length > 0;
  return true;
}

function present(source: JsonObject, key: string) {
  return Object.prototype.hasOwnProperty.call(source, key) && source[key] !== null && source[key] !== undefined;
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not reported";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try { return JSON.stringify(value); } catch { return String(value); }
}

function fileName(value: unknown) {
  if (typeof value !== "string" || !value) return "Not reported";
  const parts = value.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || value;
}

function formattedPercent(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value)) return display(value);
  const percent = value >= 0 && value <= 1 ? value * 100 : value;
  return `${percent.toFixed(1)}%`;
}

function hasFields(value: unknown): value is JsonObject {
  return Boolean(object(value) && Object.keys(value as JsonObject).length);
}

function isContractRuntimeResponse(payload: JsonObject) {
  const metadata = object(payload.metadata);
  const prediction = object(payload.prediction);
  return (typeof metadata?.framework_version === "string" && /contract/i.test(metadata.framework_version)) ||
    (typeof prediction?.prediction_model === "string" && /contract runtime/i.test(prediction.prediction_model));
}

export function WorkspaceSectionView({
  section,
  data,
  predictionRecords,
  predictionLoading,
  predictionError,
  onRetryPredictions,
  pipelineResponse,
  pipelineLoading,
  pipelineError,
  onRetryPipeline,
}: {
  section: WorkspaceSection;
  data: WorkspaceData;
  predictionRecords?: Record<string, unknown>[];
  predictionLoading?: boolean;
  predictionError?: unknown;
  onRetryPredictions?: () => void;
  pipelineResponse?: { pipeline_state: Record<string, unknown> };
  pipelineLoading?: boolean;
  pipelineError?: unknown;
  onRetryPipeline?: () => void;
}) {
  if (!data.payload) {
    return <SectionCard title="Execution details unavailable"><p className="text-sm text-muted-foreground">The selected execution has not returned workspace details yet.</p></SectionCard>;
  }
  const payload = data.payload;
  const executionId = data.executionId ?? "";
  switch (section) {
    case "overview": return <OverviewSection payload={payload} executionId={executionId} />;
    case "dataset": return <DatasetSection payload={payload} />;
    case "coverage": return <CoverageSection payload={payload} />;
    case "pipeline": return <PipelineSection payload={payload} response={pipelineResponse} loading={pipelineLoading} error={pipelineError} onRetry={onRetryPipeline} />;
    case "predictions": return <PredictionsSection payload={payload} endpointRecords={predictionRecords} loading={predictionLoading} error={predictionError} onRetry={onRetryPredictions} />;
    case "diagnostics": return <DiagnosticsSection payload={payload} />;
    case "business": return <BusinessSection payload={payload} executionId={executionId} />;
    case "decisions": return <DecisionSection payload={payload} executionId={executionId} />;
    case "reports": return <ReportsSection payload={payload} executionId={executionId} />;
    default: return null;
  }
}

function OverviewSection({ payload, executionId }: { payload: JsonObject; executionId: string }) {
  const execution = object(payload.execution) || payload;
  const dataset = object(payload.dataset) || {};
  const prediction = object(payload.prediction);
  const mapper = object(payload.framework_mapper);
  const modules = array(mapper?.mapped_sections)?.filter((item): item is string => typeof item === "string") || [];
  const risk = object(prediction?.risk_distribution);
  const riskCounts = Object.entries(risk || {}).filter((entry): entry is [string, number] => typeof entry[1] === "number" && Number.isFinite(entry[1]));
  const maxRiskCount = Math.max(0, ...riskCounts.map(([, count]) => count));
  const hasPredictionSummary = hasFields(prediction);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-xl font-semibold">Execution overview</h2><p className="mt-1 text-sm text-muted-foreground">Summary fields returned for this execution.</p></div>
        <DataSourceBadge kind="available" label="Execution detail response" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Status" value={display(execution.status ?? payload.status)} />
        <Metric label="Dataset rows" value={display(dataset.rows)} />
        <Metric label="Predicted churners" value={display(prediction?.predicted_churners)} />
        <Metric label="Average probability" value={prediction && present(prediction, "average_probability") ? formattedPercent(prediction.average_probability) : "Not reported"} />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <SectionCard title="Run identity" description="Execution metadata from the detail response.">
          <dl className="grid gap-3 sm:grid-cols-2">
            <Field label="Execution ID" value={executionId} mono />
            <Field label="Dataset" value={fileName(dataset.filename ?? payload.filename)} />
            <Field label="Sector" value={typeof dataset.sector === "string" ? sectorLabel(dataset.sector) : display(dataset.sector)} />
            <Field label="Mode" value={display(dataset.prediction_mode)} />
            <Field label="Started" value={display(execution.started_at)} />
            <Field label="Completed" value={display(execution.completed_at)} />
            <Field label="Runtime (ms)" value={display(execution.execution_time_ms)} />
            <Field label="Framework version" value={display(execution.framework_version ?? object(payload.metadata)?.framework_version)} />
          </dl>
        </SectionCard>
        <SectionCard title="Available intelligence" description="Only modules reported by the framework mapper are listed.">
          {modules.length ? <div className="flex flex-wrap gap-2">{modules.map((module) => <Badge key={module} variant="outline">{module.replaceAll("_", " ")}</Badge>)}</div> : <Unavailable text="The execution response did not report mapped intelligence modules." />}
        </SectionCard>
      </div>
      {hasPredictionSummary ? (
        <SectionCard title="Prediction summary" description="Dataset-level aggregation returned by the framework. These values are not individual customer records.">
          <div className="grid gap-5 lg:grid-cols-2">
            <dl className="grid gap-3 sm:grid-cols-2">
              <Field label="Rows in prediction output" value={display(prediction?.rows)} />
              <Field label="Predicted churners" value={display(prediction?.predicted_churners)} />
              <Field label="Prediction model" value={display(prediction?.prediction_model)} />
              <Field label="Prediction mode" value={display(prediction?.prediction_mode)} />
            </dl>
            {riskCounts.length ? (
              <div>
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Returned risk distribution · counts</p>
                <div className="space-y-3">{riskCounts.map(([name, count]) => (
                  <div key={name} className="grid grid-cols-[100px_minmax(0,1fr)_48px] items-center gap-3 text-sm">
                    <span>{name}</span><div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${maxRiskCount > 0 ? (count / maxRiskCount) * 100 : 0}%` }} /></div><span className="text-right tabular-nums">{count}</span>
                  </div>
                ))}</div>
              </div>
            ) : <Unavailable text="No risk-distribution counts were included in the prediction summary." />}
          </div>
          {present(prediction || {}, "average_probability") ? <p className="mt-4 text-xs leading-5 text-muted-foreground">Average probability is shown as returned; calibration evidence is not included in this execution response.</p> : null}
        </SectionCard>
      ) : <SectionCard title="Prediction summary"><Unavailable text="No dataset-level prediction summary was returned for this execution." /></SectionCard>}
    </div>
  );
}

function DatasetSection({ payload }: { payload: JsonObject }) {
  const dataset = object(payload.dataset);
  if (!hasFields(dataset)) return <SectionCard title="Dataset Intelligence"><Unavailable text="The execution response did not include dataset metadata." /></SectionCard>;
  return (
    <div className="space-y-5">
      <div><h2 className="text-xl font-semibold">Dataset Intelligence</h2><p className="mt-1 text-sm text-muted-foreground">Execution-time dataset metadata returned by the backend.</p></div>
      <SectionCard title="Dataset metadata" description="Values are read from the execution detail response.">
        <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <Field label="Filename" value={fileName(dataset.filename)} />
          <Field label="Sector" value={typeof dataset.sector === "string" ? sectorLabel(dataset.sector) : display(dataset.sector)} />
          <Field label="Rows reported" value={display(dataset.rows)} />
          <Field label="Columns reported" value={display(dataset.columns)} />
          <Field label="Prediction mode" value={display(dataset.prediction_mode)} />
          <Field label="Schema version" value={display(dataset.schema_version)} />
        </dl>
      </SectionCard>
      <SectionCard title="Upload profile availability" description="Dataset schema details are not included in the execution detail contract.">
        <div className="grid gap-3 sm:grid-cols-2">
          <Unavailable text="Per-column dtypes, missing-value counts, sample records, and upload validation warnings are not retrievable after upload through the current API. The upload endpoint returns these only in its POST response; no read-by-upload-ID endpoint is defined." />
          <Unavailable text="Target-column and churn-label distribution fields are not present in the execution dataset metadata. They are not inferred here." />
        </div>
      </SectionCard>
    </div>
  );
}

function CoverageSection({ payload }: { payload: JsonObject }) {
  const coverage = object(payload.coverage);
  const confidence = object(payload.concept_confidence);
  if (!hasFields(coverage) && !hasFields(confidence)) return <SectionCard title="Coverage Intelligence"><Unavailable text="Coverage and concept-confidence sections were not returned for this execution." /></SectionCard>;
  const listField = (source: JsonObject, key: string) => {
    if (!present(source, key)) return "Not reported";
    const values = array(source[key]);
    return values ? values.length ? values.map(display).join(", ") : "None reported" : display(source[key]);
  };
  const perConcept = object(confidence?.per_concept);

  return (
    <div className="space-y-5">
      <div><h2 className="text-xl font-semibold">Coverage Intelligence</h2><p className="mt-1 text-sm text-muted-foreground">Coverage measures are separate from churn probabilities and model calibration.</p></div>
      <div className="grid gap-5 xl:grid-cols-2">
        <SectionCard title="Feature coverage" description="Coverage fields directly supplied by the framework.">
          {hasFields(coverage) ? <dl className="grid gap-3 sm:grid-cols-2">
            <Field label="Coverage score" value={present(coverage, "coverage_score") ? formattedPercent(coverage.coverage_score) : "Not reported"} />
            <Field label="Coverage band" value={display(coverage.coverage_band ?? coverage.status)} />
            <Field label="Missing critical concepts" value={listField(coverage, "missing_critical")} />
            <Field label="Missing high-impact concepts" value={listField(coverage, "missing_high_impact")} />
            <Field label="Semantic matches" value={listField(coverage, "semantic_matches")} />
            <Field label="Recovered features" value={listField(coverage, "recovered_features")} />
            {present(coverage, "explanation") ? <div className="sm:col-span-2"><Field label="Coverage explanation" value={display(coverage.explanation)} /></div> : null}
          </dl> : <Unavailable text="No coverage result was returned." />}
        </SectionCard>
        <SectionCard title="Concept confidence" description="Semantic reconstructability information; not predictive confidence.">
          {hasFields(confidence) ? <>
            <dl className="grid gap-3 sm:grid-cols-2">
              <Field label="Overall concept confidence" value={present(confidence, "overall_confidence") ? formattedPercent(confidence.overall_confidence) : "Not reported"} />
              <Field label="Sector" value={display(confidence.sector)} />
              <Field label="Reconstructable concepts" value={display(confidence.reconstructable_concepts)} />
              <Field label="Total concepts" value={display(confidence.total_concepts)} />
            </dl>
            {perConcept && Object.keys(perConcept).length ? <div className="mt-4 overflow-x-auto rounded-lg border border-border"><table className="w-full text-sm"><thead className="bg-muted/35 text-left text-xs uppercase text-muted-foreground"><tr><th scope="col" className="px-3 py-2">Concept</th><th scope="col" className="px-3 py-2">Returned value</th></tr></thead><tbody className="divide-y divide-border/70">{Object.entries(perConcept).map(([name, value]) => <tr key={name}><th scope="row" className="px-3 py-2 text-left font-medium">{name}</th><td className="px-3 py-2 font-mono text-xs">{display(value)}</td></tr>)}</tbody></table></div> : <p className="mt-4 text-sm text-muted-foreground">Per-concept values were not included.</p>}
          </> : <Unavailable text="No concept-confidence section was returned." />}
        </SectionCard>
      </div>
    </div>
  );
}

function PipelineSection({ payload, response, loading, error, onRetry }: { payload: JsonObject; response?: { pipeline_state: Record<string, unknown> }; loading?: boolean; error?: unknown; onRetry?: () => void }) {
  const detailPipeline = object(payload.pipeline ?? payload.pipeline_state);
  const endpointPipeline = object(response?.pipeline_state);
  const pipeline = endpointPipeline ?? detailPipeline;
  const stages = array(pipeline?.stages)?.map(object).filter((value): value is JsonObject => Boolean(value)) || [];
  if (!stages.length && loading) return <SectionCard title="Pipeline Intelligence"><LoadingState label="Loading backend pipeline details…" /></SectionCard>;
  if (!stages.length && error) return <SectionCard title="Pipeline Intelligence" description="Pipeline details are independent from the execution summary."><ErrorBanner error={error} onRetry={onRetry} /></SectionCard>;
  if (!stages.length) return <SectionCard title="Pipeline Intelligence"><Unavailable text="Neither the execution detail nor pipeline endpoint returned stage-level details. No client-generated stages or progress are shown." /></SectionCard>;
  return (
    <div className="space-y-5">
      <div><h2 className="text-xl font-semibold">Pipeline Intelligence</h2><p className="mt-1 text-sm text-muted-foreground">Stage names, statuses, descriptions, and timings come from the backend pipeline summary.</p></div>
      <SectionCard title="Execution stages" description={`Backend summary: ${display(pipeline?.overall_status)} · ${display(pipeline?.completed)} completed of ${display(pipeline?.total_stages)} reported`}>
        <ol className="space-y-3">
          {stages.map((stage, index) => (
            <li key={String(stage.id ?? stage.name ?? index)} className="grid gap-3 rounded-lg border border-border bg-background p-4 sm:grid-cols-[minmax(0,1fr)_auto]">
              <div><div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{display(stage.name)}</span><Badge variant="outline">{display(stage.status)}</Badge></div>{present(stage, "description") ? <p className="mt-2 text-sm leading-5 text-muted-foreground">{display(stage.description)}</p> : null}</div>
              {present(stage, "execution_time") ? <p className="text-xs tabular-nums text-muted-foreground">{display(stage.execution_time)} ms</p> : <p className="text-xs text-muted-foreground">Timing not reported</p>}
            </li>
          ))}
        </ol>
      </SectionCard>
    </div>
  );
}

function PredictionsSection({ payload, endpointRecords, loading, error, onRetry }: { payload: JsonObject; endpointRecords?: Record<string, unknown>[]; loading?: boolean; error?: unknown; onRetry?: () => void }) {
  const detailRows = array(payload.predictions)?.map(object).filter((value): value is JsonObject => Boolean(value)) || [];
  const apiRows = endpointRecords?.map(object).filter((value): value is JsonObject => Boolean(value)) || [];
  const rows = detailRows.length ? detailRows : apiRows;
  const hasDetailRows = Array.isArray(payload.predictions);
  const rowsSource = detailRows.length ? "Execution detail" : apiRows.length ? "Predictions endpoint" : null;
  const summary = object(payload.prediction);
  const risk = object(summary?.risk_distribution);
  const riskCounts = Object.entries(risk || {}).filter((entry): entry is [string, number] => typeof entry[1] === "number" && Number.isFinite(entry[1]) && entry[1] >= 0);
  const riskData = riskCounts.map(([name, count]) => ({ name: name.replaceAll("_", " "), count }));
  return (
    <div className="space-y-5">
      <div><h2 className="text-xl font-semibold">Predictions</h2><p className="mt-1 text-sm text-muted-foreground">Record values are shown as returned by the framework. They are not calibrated or independently validated here.</p></div>
      {hasFields(summary) ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Rows" value={display(summary.rows)} /><Metric label="Predicted churners" value={display(summary.predicted_churners)} /><Metric label="Average probability" value={present(summary, "average_probability") ? formattedPercent(summary.average_probability) : "Not reported"} /><Metric label="Prediction model" value={display(summary.prediction_model)} />
      </div> : null}
      <SectionCard title="Risk distribution" description="Counts are plotted only when the execution returned numeric risk-category counts.">
        {riskData.length ? <div className="min-w-0"><BarChart data={riskData} xDataKey="name" aspectRatio="2.3 / 1" margin={{ top: 18, right: 16, bottom: 28, left: 16 }} animationDuration={500}><Grid horizontal /><Bar dataKey="count" fill="var(--chart-line-primary)" lineCap={5} showValue animate /><BarXAxis showAllLabels maxLabels={8} /><ChartTooltip /></BarChart><p className="mt-2 text-[10px] text-muted-foreground">Returned category counts only; no individual risk levels are inferred from aggregate probabilities.</p><ul className="sr-only" aria-label="Returned risk distribution counts">{riskData.map((item) => <li key={item.name}>{item.name}: {item.count}</li>)}</ul></div> : <Unavailable text="This execution did not return a numeric risk distribution. No chart is inferred from the average probability." />}
      </SectionCard>
      {loading && !rows.length ? <SectionCard title="Record-level predictions"><LoadingState label="Loading prediction records…" /></SectionCard> : null}
      {error && !rows.length ? <SectionCard title="Record-level predictions" description="The execution summary remains available even when record-level predictions cannot be loaded."><ErrorBanner error={error} onRetry={onRetry} /></SectionCard> : null}
      {!loading && !error && !rowsSource ? <SectionCard title="Record-level predictions"><Unavailable text={hasDetailRows ? "The execution returned no record-level prediction rows." : "Neither the execution detail nor the predictions endpoint returned record-level rows."} /></SectionCard> : null}
      {rowsSource && rows.length ? <PredictionsTable rows={rows} sourceLabel={rowsSource} /> : null}
    </div>
  );
}

function PredictionsTable({ rows, sourceLabel }: { rows: JsonObject[]; sourceLabel: string }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState("");
  const [sortAscending, setSortAscending] = useState(true);
  const columns = useMemo(() => Array.from(new Set(rows.flatMap((row) => Object.keys(row)))), [rows]);
  const filtered = useMemo(() => rows.filter((row) => !search.trim() || Object.values(row).some((value) => display(value).toLowerCase().includes(search.toLowerCase()))), [rows, search]);
  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    return [...filtered].sort((left, right) => {
      const a = left[sortKey]; const b = right[sortKey];
      const result = typeof a === "number" && typeof b === "number" ? a - b : display(a).localeCompare(display(b), undefined, { numeric: true, sensitivity: "base" });
      return sortAscending ? result : -result;
    });
  }, [filtered, sortKey, sortAscending]);
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const activePage = Math.min(page, totalPages);
  const visible = sorted.slice((activePage - 1) * PAGE_SIZE, activePage * PAGE_SIZE);

  return (
    <SectionCard title="Record-level predictions" description="Search, sort, and paginate the returned records. Pagination is local because the API has no paging parameters." action={<DataSourceBadge kind="historical" label={`${sourceLabel} · ${rows.length.toLocaleString()} rows`} />}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <label className="relative block w-full max-w-sm"><span className="sr-only">Search prediction records</span><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><Input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search returned values…" className="pl-9" /></label>
        <p className="text-xs text-muted-foreground">{sorted.length.toLocaleString()} matching records</p>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="bg-muted/35 text-left text-xs uppercase tracking-wide text-muted-foreground"><tr>{columns.map((column) => <th key={column} scope="col" aria-sort={sortKey === column ? (sortAscending ? "ascending" : "descending") : "none"} className="whitespace-nowrap px-3 py-2"><button type="button" className="inline-flex items-center gap-1 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => { if (sortKey === column) setSortAscending((value) => !value); else { setSortKey(column); setSortAscending(true); } }}>{column}{sortKey === column ? sortAscending ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" /> : null}</button></th>)}</tr></thead>
          <tbody className="divide-y divide-border/70">{visible.map((row, index) => <tr key={`${String(row.CustomerID ?? row.customer_id ?? row.id ?? "record")}-${index}`} className="align-top hover:bg-muted/20">{columns.map((column) => <td key={column} className="max-w-[360px] whitespace-nowrap px-3 py-2 font-mono text-xs">{display(row[column])}</td>)}</tr>)}</tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3"><p className="text-xs text-muted-foreground">Page {activePage} of {totalPages}</p><div className="flex gap-2"><Button variant="outline" size="sm" disabled={activePage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button><Button variant="outline" size="sm" disabled={activePage >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>Next</Button></div></div>
      <p className="mt-3 text-xs leading-5 text-muted-foreground">Rows are displayed without default risk tiers, decisions, explanations, or substitute values. Probability-like output is shown as supplied; calibration information is not part of this response.</p>
    </SectionCard>
  );
}

function DiagnosticsSection({ payload }: { payload: JsonObject }) {
  const diagnostics = object(payload.diagnostics);
  const semantic = object(payload.semantic_intelligence);
  const featureEngineering = object(payload.feature_engineering);
  const quality = object(payload.quality);
  const explanation = object(payload.prediction_explanation);
  const executionState = object(payload.execution_state);
  const warnings = array(payload.warnings);
  const available = [diagnostics, semantic, featureEngineering, quality, explanation, executionState].some(populated) || warnings !== null;
  if (!available) return <SectionCard title="Diagnostic Intelligence"><Unavailable text="No diagnostics, semantic analysis, quality summary, or explanation narrative was returned for this execution." /></SectionCard>;
  const timings = object(diagnostics?.stage_timings);
  return (
    <div className="space-y-5">
      <div><h2 className="text-xl font-semibold">Diagnostic Intelligence</h2><p className="mt-1 text-sm text-muted-foreground">Backend diagnostic and semantic evidence is distinct from prediction output and does not imply causality.</p></div>
      {hasFields(explanation) ? <SectionCard title="Dataset-level explanation narrative" description="Framework-generated narrative; not a per-customer SHAP explanation.">
        <div className="space-y-3">{present(explanation, "headline") ? <p className="text-base font-semibold">{display(explanation.headline)}</p> : null}{present(explanation, "reason_text") ? <p className="text-sm leading-6">{display(explanation.reason_text)}</p> : null}{present(explanation, "recommendation_text") ? <p className="text-sm leading-6 text-muted-foreground">{display(explanation.recommendation_text)}</p> : null}<dl className="grid gap-3 sm:grid-cols-2">{present(explanation, "overall_business_health") ? <Field label="Reported business health" value={display(explanation.overall_business_health)} /> : null}{present(explanation, "overall_customer_risk") ? <Field label="Reported customer risk" value={display(explanation.overall_customer_risk)} /> : null}</dl>{array(explanation.dominant_findings)?.length ? <div className="flex flex-wrap gap-2">{(explanation.dominant_findings as unknown[]).map((finding, index) => <Badge key={`${display(finding)}-${index}`} variant="outline">{display(finding)}</Badge>)}</div> : null}</div>
      </SectionCard> : null}
      {hasFields(quality) ? <SectionCard title="Quality summary" description="Quality fields returned by the framework; missing properties are not interpreted as passing.">
        <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{["overall_passed", "leakage_detected", "leakage_flagged", "leakage_warned", "failed_columns", "duplicate_columns", "duplicate_info"].filter((key) => present(quality, key)).map((key) => <Field key={key} label={key.replaceAll("_", " ")} value={display(quality[key])} />)}</dl>
      </SectionCard> : null}
      {timings && Object.keys(timings).length ? <SectionCard title="Diagnostic timings" description="Only timing entries included by the backend are listed."><dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(timings).map(([name, value]) => <Field key={name} label={name.replaceAll("_", " ")} value={`${display(value)} s`} />)}</dl></SectionCard> : null}
      {warnings !== null ? <SectionCard title="Execution warnings">{warnings.length ? <ul className="list-disc space-y-1 pl-5 text-sm">{warnings.map((warning, index) => <li key={`${display(warning)}-${index}`}>{display(warning)}</li>)}</ul> : <p className="text-sm text-muted-foreground">The execution response included no warnings.</p>}</SectionCard> : null}
      {hasFields(semantic) ? <JsonSection title="Semantic intelligence" description="Framework-returned business meaning, mapping, graph, and context diagnostics." value={semantic} /> : null}
      {hasFields(featureEngineering) ? <JsonSection title="Feature engineering" description="Feature manifest and resolution details returned for this execution." value={featureEngineering} /> : null}
      {hasFields(diagnostics) ? <JsonSection title="Raw diagnostic payload" description="Additional diagnostic fields are shown as returned." value={diagnostics} /> : null}
      {hasFields(executionState) ? <JsonSection title="Execution state details" description="Additional execution-state fields supplied by the backend." value={executionState} /> : null}
      <p className="text-xs text-muted-foreground">The execution API does not return SHAP values or local per-record feature contributions. This view does not infer them from narrative text.</p>
    </div>
  );
}

function BusinessSection({ payload, executionId }: { payload: JsonObject; executionId: string }) {
  const prediction = object(payload.prediction);
  const dataset = object(payload.dataset);
  const explanation = object(payload.prediction_explanation);
  const coverage = object(payload.coverage);
  const quality = object(payload.quality);
  const risk = object(prediction?.risk_distribution);
  const riskCounts = Object.entries(risk || {}).filter((entry): entry is [string, number] => typeof entry[1] === "number" && Number.isFinite(entry[1]) && entry[1] >= 0);
  const returnedRiskTotal = riskCounts.reduce((total, [, count]) => total + count, 0);
  const contractRuntime = isContractRuntimeResponse(payload);
  const findings = array(explanation?.dominant_findings)?.filter((item) => item !== null && item !== undefined) || [];
  const returnedRows = useMemo(() => (array(payload.predictions) || []).map((value, index) => {
    const record = object(value);
    if (!record) return null;
    const customer = record.CustomerID ?? record.customer_id ?? record.customerId;
    const riskLevel = record.Risk_Level ?? record.risk_level ?? record.riskTier;
    const probability = record.Churn_Probability ?? record.churn_probability ?? record.churnProbability;
    const numericProbability = typeof probability === "number" ? probability : typeof probability === "string" && probability.trim() ? Number(probability) : Number.NaN;
    return { key: `${customer == null ? "returned-row" : String(customer)}-${index}`, customer: customer == null ? "Identifier not returned" : String(customer), riskLevel: typeof riskLevel === "string" ? riskLevel : "", probability: Number.isFinite(numericProbability) ? numericProbability : null, predicted: record.Predicted_Churn ?? record.predicted_churn ?? record.predictedChurn };
  }).filter((row): row is NonNullable<typeof row> => row !== null), [payload.predictions]);
  const [riskFilter, setRiskFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sortDirection, setSortDirection] = useState<"ascending" | "descending">("descending");
  const [sortKey, setSortKey] = useState<"probability" | "customer">("probability");
  const filteredRows = useMemo(() => returnedRows
    .filter((row) => riskFilter === "all" || row.riskLevel.toLowerCase() === riskFilter.toLowerCase())
    .filter((row) => !search.trim() || `${row.customer} ${row.riskLevel} ${display(row.predicted)}`.toLowerCase().includes(search.trim().toLowerCase()))
    .sort((left, right) => {
      const comparison = sortKey === "customer"
        ? left.customer.localeCompare(right.customer)
        : (left.probability ?? Number.NEGATIVE_INFINITY) - (right.probability ?? Number.NEGATIVE_INFINITY);
      return sortDirection === "ascending" ? comparison : -comparison;
    }), [returnedRows, riskFilter, search, sortDirection, sortKey]);
  const hasBusinessEvidence = hasFields(prediction) || hasFields(explanation) || hasFields(coverage) || hasFields(quality);
  if (!hasBusinessEvidence) return <SectionCard title="Business Intelligence"><Unavailable text="This execution did not return prediction, explanation, coverage, or quality evidence for business interpretation." /></SectionCard>;

  const workspaceHref = (tab: WorkspaceSection) => `/workspace?execution_id=${encodeURIComponent(executionId)}&tab=${tab}`;
  const toggleSort = (key: "probability" | "customer") => {
    setSortDirection((current) => sortKey === key && current === "descending" ? "ascending" : "descending");
    setSortKey(key);
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Business Intelligence</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">An execution-scoped view of returned churn summaries, reported risk categories, and analytical observations. It does not estimate realized business impact.</p></div><div className="flex flex-wrap gap-2">{contractRuntime ? <DataSourceBadge kind="unverified" label="Contract runtime response" /> : null}<DataSourceBadge kind="historical" label="Selected execution" /></div></div>
      {contractRuntime ? <div role="note" className="rounded-xl border border-warning/35 bg-warning/5 px-4 py-3 text-sm leading-6 text-muted-foreground">The execution identifies a contract runtime. Returned counts and probabilities are API response values and do not establish validated production model performance or calibration.</div> : null}

      <section aria-label="Execution business summary" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Sector" value={typeof dataset?.sector === "string" ? sectorLabel(dataset.sector) : "Not reported"} />
        <Metric label="Rows analyzed" value={display(prediction?.rows)} />
        <Metric label="Predicted churners" value={display(prediction?.predicted_churners)} />
        <Metric label="Average churn probability" value={prediction && present(prediction, "average_probability") ? formattedPercent(prediction.average_probability) : "Not reported"} />
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(280px,.75fr)]">
        <SectionCard title="Returned risk distribution" description="Counts come directly from this execution. They are risk categories, not observed churn outcomes." action={<DataSourceBadge kind="available" label="Execution result" />}>
          {riskCounts.length ? <>
            <div className="min-w-0"><BarChart data={riskCounts.map(([name, count]) => ({ name: name.replaceAll("_", " "), count }))} xDataKey="name" aspectRatio="2.35 / 1" margin={{ top: 18, right: 16, bottom: 30, left: 16 }} animationDuration={550}><Grid horizontal /><Bar dataKey="count" fill="var(--chart-1)" lineCap={5} showValue animate /><BarXAxis showAllLabels maxLabels={8} /><ChartTooltip /></BarChart></div>
            <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[340px] text-left text-sm"><caption className="sr-only">Returned risk category counts and share of returned categories</caption><thead><tr className="border-b border-border text-xs text-muted-foreground"><th scope="col" className="py-2 pr-3 font-medium">Returned category</th><th scope="col" className="py-2 pr-3 text-right font-medium">Records</th><th scope="col" className="py-2 text-right font-medium">Share of category counts</th></tr></thead><tbody>{riskCounts.map(([name, count]) => <tr key={name} className="border-b border-border/60"><th scope="row" className="py-2 pr-3 font-medium capitalize">{name.replaceAll("_", " ")}</th><td className="py-2 pr-3 text-right tabular-nums">{count.toLocaleString()}</td><td className="py-2 text-right tabular-nums">{returnedRiskTotal ? `${(count / returnedRiskTotal * 100).toFixed(1)}%` : "Not available"}</td></tr>)}</tbody></table></div>
            <p className="mt-3 text-xs leading-5 text-muted-foreground">Share is derived as category count divided by the sum of returned category counts ({returnedRiskTotal.toLocaleString()}). It may differ from rows analyzed if the backend categories do not cover every row.</p>
          </> : <Unavailable text="Risk-category counts were not returned. No distribution is inferred from the average probability." />}
        </SectionCard>

        <div className="space-y-5">
          <SectionCard title="Execution context" description="Fields reported for the selected run.">
            <dl className="grid gap-3">{typeof dataset?.filename === "string" ? <Field label="Dataset" value={fileName(dataset.filename)} /> : null}{typeof dataset?.sector === "string" ? <Field label="Reported sector" value={sectorLabel(dataset.sector)} /> : null}<Field label="Execution ID" value={executionId} mono /></dl>
            <div className="mt-4 flex flex-wrap gap-2"><Link href={workspaceHref("predictions")} className="text-sm font-medium text-primary underline-offset-4 hover:underline">Explore returned records</Link><Link href={workspaceHref("diagnostics")} className="text-sm font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">Review diagnostics</Link></div>
          </SectionCard>
          <SectionCard title="Business impact" description="Business value requires customer economics and observed intervention outcomes.">
            <Unavailable text="Revenue at risk, customer lifetime value, campaign cost, retention savings, ROI, and realized retention outcomes are not returned by this execution API." />
          </SectionCard>
        </div>
      </div>

      <SectionCard title="Analytical observations" description="Framework narrative and data-quality context, when included in the execution response." action={<DataSourceBadge kind="available" label="Framework evidence" />}>
        {hasFields(explanation) ? <div className="space-y-3">
          {present(explanation, "headline") ? <h3 className="text-base font-semibold">{display(explanation.headline)}</h3> : null}
          {present(explanation, "reason_text") ? <p className="text-sm leading-6">{display(explanation.reason_text)}</p> : null}
          {findings.length ? <div><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Reported findings</p><ul className="space-y-2">{findings.map((finding, index) => <li key={`${display(finding)}-${index}`} className="rounded-lg border border-border bg-muted/10 px-3 py-2 text-sm">{display(finding)}</li>)}</ul></div> : <Unavailable text="No dominant findings were returned." />}
        </div> : <Unavailable text="No dataset-level explanation narrative or dominant findings were returned." />}
        {hasFields(coverage) || hasFields(quality) ? <div className="mt-4 grid gap-3 sm:grid-cols-2">{hasFields(coverage) ? <Field label="Feature coverage" value={present(coverage, "coverage_score") ? formattedPercent(coverage.coverage_score) : display(coverage.coverage_band ?? coverage.status)} /> : null}{hasFields(quality) ? <Field label="Quality assessment" value={present(quality, "overall_passed") ? display(quality.overall_passed) : "Assessment returned; outcome not specified"} /> : null}</div> : null}
      </SectionCard>

      <SectionCard title="Customer risk records" description="Search and filter only fields returned on prediction records. Risk labels are not derived from probability values." action={<DataSourceBadge kind={returnedRows.length ? "available" : "unavailable"} label={returnedRows.length ? `${returnedRows.length.toLocaleString()} returned records` : "Records unavailable"} />}>
        {returnedRows.length ? <>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><label className="w-full max-w-sm"><span className="sr-only">Search returned customer records</span><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search customer, risk, or outcome…" /></label><div className="flex flex-wrap gap-2" aria-label="Filter by returned risk category"><button type="button" aria-pressed={riskFilter === "all"} onClick={() => setRiskFilter("all")} className={`rounded-full border px-3 py-1.5 text-xs font-medium ${riskFilter === "all" ? "border-foreground bg-foreground text-background" : "border-border text-muted-foreground hover:text-foreground"}`}>All records</button>{riskCounts.map(([name, count]) => <button key={name} type="button" aria-pressed={riskFilter.toLowerCase() === name.toLowerCase()} onClick={() => setRiskFilter(name)} className={`rounded-full border px-3 py-1.5 text-xs font-medium capitalize ${riskFilter.toLowerCase() === name.toLowerCase() ? "border-foreground bg-foreground text-background" : "border-border text-muted-foreground hover:text-foreground"}`}>{name.replaceAll("_", " ")} · {count.toLocaleString()}</button>)}</div></div>
          <div className="mt-4 overflow-x-auto rounded-xl border border-border"><table className="w-full min-w-[560px] text-left text-sm"><caption className="sr-only">Customer-level risk fields returned by the selected execution</caption><thead className="bg-muted/30"><tr><th scope="col" className="px-3 py-3"><button type="button" onClick={() => toggleSort("customer")} className="font-semibold hover:text-primary">Customer identifier{sortKey === "customer" ? sortDirection === "ascending" ? " ↑" : " ↓" : ""}</button></th><th scope="col" className="px-3 py-3 font-semibold">Returned risk level</th><th scope="col" className="px-3 py-3 text-right"><button type="button" onClick={() => toggleSort("probability")} className="font-semibold hover:text-primary">Returned probability{sortKey === "probability" ? sortDirection === "ascending" ? " ↑" : " ↓" : ""}</button></th><th scope="col" className="px-3 py-3 font-semibold">Returned outcome</th></tr></thead><tbody>{filteredRows.slice(0, 12).map((row) => <tr key={row.key} className="border-t border-border/70"><th scope="row" className="max-w-[220px] truncate px-3 py-3 font-mono text-xs font-medium" title={row.customer}>{row.customer}</th><td className="px-3 py-3">{row.riskLevel || "Not returned"}</td><td className="px-3 py-3 text-right tabular-nums">{row.probability === null ? "Not returned" : formattedPercent(row.probability)}</td><td className="px-3 py-3">{display(row.predicted)}</td></tr>)}</tbody></table></div>
          <p className="mt-3 text-xs text-muted-foreground">Showing {Math.min(filteredRows.length, 12)} of {filteredRows.length.toLocaleString()} matching returned records. Customer-level strategy effectiveness and outcomes are not available.</p>
        </> : <Unavailable text="This execution did not include customer-level prediction rows. Use the Predictions section if a separate records endpoint is available; no customer records are synthesized here." />}
      </SectionCard>
    </div>
  );
}

function DecisionSection({ payload, executionId }: { payload: JsonObject; executionId: string }) {
  const decision = object(payload.decision);
  const explanation = object(payload.prediction_explanation);
  const adaptive = object(payload.adaptive_business);
  const contextAssessment = object(adaptive?.assessment);
  const prediction = object(payload.prediction);
  const contractRuntime = isContractRuntimeResponse(payload);
  const signals = array(adaptive?.signals)?.map(object).filter((signal): signal is JsonObject => Boolean(signal)) || [];
  const warnings = [...(array(decision?.warnings) || []), ...(array(payload.warnings) || [])].filter((item) => item !== null && item !== undefined);
  const recommendation = decision?.recommended_action ?? explanation?.recommendation_text;
  const recommendationReturned = typeof recommendation === "string" && recommendation.trim().length > 0;
  const contextHref = (tab: WorkspaceSection) => `/workspace?execution_id=${encodeURIComponent(executionId)}&tab=${tab}`;
  const hasDecisionEvidence = hasFields(decision) || hasFields(explanation) || hasFields(adaptive);
  if (!hasDecisionEvidence) return <SectionCard title="Decision Intelligence"><Unavailable text="No decision, recommendation, explanation, or adaptive business context was returned for this execution." /></SectionCard>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Decision Intelligence</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">Review the framework recommendation alongside its returned analytical evidence and business context. Recommendations are decision support, not approved customer actions.</p></div><DataSourceBadge kind={contractRuntime ? "unverified" : "available"} label={contractRuntime ? "Contract runtime response" : "Execution response"} /></div>
      {contractRuntime ? <div role="note" className="rounded-xl border border-warning/35 bg-warning/5 px-4 py-3 text-sm leading-6 text-muted-foreground">This execution identifies a contract runtime. Its readiness, confidence, risk, and recommendation fields are contract outputs, not evidence of validated model performance or causal business impact.</div> : null}

      {hasFields(decision) ? <section aria-label="Decision assessment summary" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{present(decision, "decision_readiness") ? <Metric label="Decision readiness" value={display(decision.decision_readiness)} /> : null}{present(decision, "risk_level") ? <Metric label="Assessment risk level" value={display(decision.risk_level)} /> : null}{present(decision, "evidence_strength") ? <Metric label="Evidence strength" value={formattedPercent(decision.evidence_strength)} /> : null}{present(decision, "overall_confidence") ? <Metric label="Decision assessment confidence" value={formattedPercent(decision.overall_confidence)} /> : null}</section> : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(280px,.8fr)]">
        <SectionCard title="Framework recommendation" description="Recommendation text is presented exactly as returned by the analysis service; no strategy or outcome is inferred." action={<DataSourceBadge kind={recommendationReturned ? "available" : "unavailable"} label={recommendationReturned ? "Recommendation returned" : "No recommendation"} />}>
          {recommendationReturned ? <div className="space-y-4"><p className="text-lg font-medium leading-7">{recommendation}</p>{present(explanation || {}, "headline") ? <p className="text-sm font-semibold text-muted-foreground">{display(explanation?.headline)}</p> : null}{present(explanation || {}, "reason_text") ? <p className="text-sm leading-6 text-muted-foreground">{display(explanation?.reason_text)}</p> : null}<details className="group rounded-xl border border-border bg-muted/10"><summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold marker:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">View recommendation evidence<span className="float-right text-muted-foreground group-open:rotate-180" aria-hidden="true">⌄</span></summary><div className="space-y-3 border-t border-border p-4">{array(explanation?.dominant_findings)?.length ? <div><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Reported findings</p><ul className="list-disc space-y-1 pl-5 text-sm">{(explanation?.dominant_findings as unknown[]).map((finding, index) => <li key={`${display(finding)}-${index}`}>{display(finding)}</li>)}</ul></div> : <Unavailable text="No dominant findings were included with this recommendation." />}{present(decision || {}, "adaptive_context") ? <Field label="Adaptive context summary" value={display(decision?.adaptive_context)} /> : null}</div></details></div> : <Unavailable text="The execution contains no recommendation text. Review the available evidence without inferring an action." />}
        </SectionCard>

        <SectionCard title="Decision lifecycle" description="This interface reports only states evidenced by the execution API.">
          <ol className="grid gap-3">
            <LifecycleStep title="Prediction" status={hasFields(prediction) ? "Returned" : "Not reported"} detail="Execution-level prediction summary" available={hasFields(prediction)} />
            <LifecycleStep title="Recommendation" status={recommendationReturned ? "Returned" : "Not reported"} detail="Proposed guidance; no approval implied" available={recommendationReturned} />
            <LifecycleStep title="Approval" status="Not available" detail="No approval workflow or approval state is exposed" available={false} />
            <LifecycleStep title="Action initiated" status="Not available" detail="No action execution endpoint is exposed" available={false} />
            <LifecycleStep title="Action outcome" status="Not available" detail="No completion, failure, or retention outcome is returned" available={false} />
          </ol>
        </SectionCard>
      </div>

      <SectionCard title="Business context signals" description="External context supplied to or returned by this execution; signal confidence is not churn probability or causal evidence." action={<DataSourceBadge kind={signals.length ? "available" : "unavailable"} label={signals.length ? `${signals.length} returned signals` : "No signals returned"} />}>
        {contextAssessment ? <section className="mb-4 grid gap-3 sm:grid-cols-3" aria-label="ABIL context assessment"><Metric label="Context priority" value={display(contextAssessment.priority)} /><Metric label="Dominant context signal" value={display(contextAssessment.dominant_driver)} /><Metric label="Signals evaluated" value={display(contextAssessment.signals_evaluated)} /></section> : null}
        {contextAssessment ? <p className="mb-4 text-xs leading-5 text-muted-foreground">Context priority is ranked from supplied signal severity. It is separate from model churn probability, customer-level prediction, and causal evidence.</p> : null}
        {signals.length ? <div className="grid gap-3 lg:grid-cols-2">{signals.map((signal, index) => <article key={`${display(signal.name)}-${index}`} className="rounded-xl border border-border bg-muted/10 p-4"><div className="flex flex-wrap items-start justify-between gap-2"><h3 className="font-semibold">{display(signal.name)}</h3>{present(signal, "impact") ? <Badge variant="outline">Reported impact · {display(signal.impact)}</Badge> : null}</div>{present(signal, "value") ? <p className="mt-3 text-sm leading-6">{display(signal.value)}</p> : null}<dl className="mt-3 grid gap-2 sm:grid-cols-2">{present(signal, "confidence") ? <Field label="Signal confidence" value={formattedPercent(signal.confidence)} /> : null}{present(signal, "department") ? <Field label="Department" value={display(signal.department)} /> : null}{present(signal, "priority") ? <Field label="Supplied priority" value={display(signal.priority)} /> : null}{present(signal, "source") ? <Field label="Source" value={display(signal.source)} /> : null}</dl>{present(signal, "action") ? <div className="mt-3 border-t border-border pt-3"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Rule-based follow-up</p><p className="mt-1 text-sm leading-6">{display(signal.action)}</p>{present(signal, "rationale") ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{display(signal.rationale)}</p> : null}{present(signal, "limitations") ? <p className="mt-1 text-xs leading-5 text-muted-foreground">{display(signal.limitations)}</p> : null}{present(signal, "source_recommendation") ? <details className="mt-2"><summary className="cursor-pointer text-xs font-medium text-muted-foreground">View supplied recommendation</summary><p className="mt-1 text-xs leading-5 text-muted-foreground">{display(signal.source_recommendation)}</p></details> : null}</div> : present(signal, "recommendation_influence") ? <p className="mt-3 border-t border-border pt-3 text-xs leading-5 text-muted-foreground">Supplied recommendation: {display(signal.recommendation_influence)}</p> : null}</article>)}</div> : <Unavailable text="No adaptive business signals were returned for this execution." />}
      </SectionCard>

      {warnings.length ? <SectionCard title="Returned warnings"><ul className="list-disc space-y-1 pl-5 text-sm leading-5">{warnings.map((warning, index) => <li key={`${display(warning)}-${index}`}>{display(warning)}</li>)}</ul></SectionCard> : null}
      <SectionCard title="Available decision evidence" description="Open the source sections associated with this execution.">
        <div className="grid gap-3 sm:grid-cols-3"><Link href={contextHref("predictions")} className="rounded-xl border border-border bg-muted/10 p-4 text-sm font-medium transition-colors hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Review returned predictions <span aria-hidden="true">→</span></Link><Link href={contextHref("diagnostics")} className="rounded-xl border border-border bg-muted/10 p-4 text-sm font-medium transition-colors hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Review diagnostics <span aria-hidden="true">→</span></Link><Link href={contextHref("reports")} className="rounded-xl border border-border bg-muted/10 p-4 text-sm font-medium transition-colors hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Open execution reports <span aria-hidden="true">→</span></Link></div>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">Assessment confidence and evidence strength are framework-reported values, not calibrated churn probabilities. The API does not expose recommendation approval, action execution, or measured retention outcomes.</p>
      </SectionCard>
    </div>
  );
}

function LifecycleStep({ title, status, detail, available }: { title: string; status: string; detail: string; available: boolean }) {
  return <li className="min-w-0 rounded-xl border border-border bg-muted/10 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p><p className={`mt-2 text-sm font-semibold ${available ? "text-foreground" : "text-muted-foreground"}`}>{status}</p><p className="mt-1 text-xs leading-5 text-muted-foreground">{detail}</p></li>;
}

function ReportsSection({ payload, executionId }: { payload: JsonObject; executionId: string }) {
  const refs = array(payload.reports)?.map(object).filter((value): value is JsonObject => Boolean(value)) || [];
  const texts = object(payload.report_texts);
  const textEntries = Object.entries(texts || {}).filter((entry): entry is [string, string] => typeof entry[1] === "string" && Boolean(entry[1]));
  if (!refs.length && !textEntries.length) return <SectionCard title="Reports"><Unavailable text="No report references or report text were returned for this execution." /><Link href={`/reports?execution_id=${encodeURIComponent(executionId)}`} className="mt-3 inline-block text-sm font-medium text-primary underline-offset-4 hover:underline">Open Report Center for this execution</Link></SectionCard>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Reports</h2><p className="mt-1 text-sm text-muted-foreground">Only report references and text associated with this execution are shown.</p></div><Link href={`/reports?execution_id=${encodeURIComponent(executionId)}`} className="text-sm font-medium text-primary underline-offset-4 hover:underline">Open Report Center</Link></div>
      {refs.length ? <SectionCard title="Report references" description="Reference metadata as returned by the API.">
        <div className="space-y-3">{refs.map((report, index) => <article key={String(report.id ?? index)} className="grid gap-2 rounded-lg border border-border bg-background p-4 sm:grid-cols-[minmax(0,1fr)_auto]">
          <div><h3 className="font-semibold">{display(report.title)}</h3><p className="mt-1 text-xs text-muted-foreground">Type: {display(report.type)}</p>{present(report, "location") ? <p className="mt-1 break-all font-mono text-xs text-muted-foreground">Location: {display(report.location)}</p> : null}</div>
          <p className="text-xs text-muted-foreground">API timestamp: {display(report.created_at)}</p>
        </article>)}</div>
        <p className="mt-3 text-xs text-muted-foreground">Locations are displayed as metadata and are not treated as download URLs.</p>
      </SectionCard> : null}
      {textEntries.length ? <SectionCard title="Returned report text" description="Report text returned for this execution; downloads contain this API text only.">
        <div className="space-y-3">{textEntries.map(([name, text]) => <details key={name} className="group rounded-lg border border-border bg-background">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3"><span className="font-medium">{name.replaceAll("_", " ")}</span><span className="text-xs text-muted-foreground">View report text</span></summary>
          <div className="border-t border-border p-3"><Button type="button" size="sm" variant="outline" onClick={() => downloadText(name, text)}><Download className="mr-2 h-4 w-4" />Download returned text</Button></div>
          <pre className="max-h-[560px] overflow-auto whitespace-pre-wrap border-t border-border bg-muted/10 p-4 font-mono text-xs leading-5">{text}</pre>
        </details>)}</div>
      </SectionCard> : null}
    </div>
  );
}

function downloadText(name: string, text: string) {
  const safeName = name.toLowerCase().replace(/[^a-z0-9-_]+/g, "-").replace(/^-+|-+$/g, "") || "ucif-report";
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${safeName}.txt`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function JsonSection({ title, description, value }: { title: string; description: string; value: JsonObject }) {
  return <SectionCard title={title} description={description}><pre className="max-h-[520px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-muted/15 p-4 font-mono text-xs leading-5">{JSON.stringify(value, null, 2)}</pre></SectionCard>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-border bg-card p-4"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-3 break-words text-xl font-semibold tabular-nums">{value}</p></div>;
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="min-w-0 rounded-lg border border-border bg-muted/10 p-3"><dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</dt><dd className={`mt-1 break-words text-sm ${mono ? "font-mono text-xs" : "font-medium"}`}>{value}</dd></div>;
}

function Unavailable({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-border bg-muted/10 p-4 text-sm leading-6 text-muted-foreground">{text}</div>;
}
