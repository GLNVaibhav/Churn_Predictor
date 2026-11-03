"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowRight, Download, FileJson2, FileSpreadsheet, FileText, Printer } from "lucide-react";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { ErrorBanner, EmptyState, LoadingState } from "@/components/shared/query-states";
import { DataSourceBadge } from "@/components/shared/data-source-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAnalysisWorkspace } from "@/lib/hooks/use-analysis-workspace";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { useLatestRunSelection } from "@/lib/hooks/use-latest-run-selection";
import { useExecutionContext } from "@/lib/context/execution-context";
import { sectorLabel } from "@/lib/constants/sectors";

type JsonObject = Record<string, unknown>;

function object(value: unknown): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : null;
}

function array(value: unknown): unknown[] | null {
  return Array.isArray(value) ? value : null;
}

function display(value: unknown) {
  if (value === null || value === undefined || value === "") return "Not reported";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try { return JSON.stringify(value); } catch { return String(value); }
}

function formatBriefValue(label: string, value: unknown) {
  if (label === "Average probability" && typeof value === "number" && Number.isFinite(value)) {
    const percent = value >= 0 && value <= 1 ? value * 100 : value;
    return `${percent.toFixed(1)}%`;
  }
  return display(value);
}

function timestamp(value: unknown) {
  if (typeof value !== "string" || !value) return "Timestamp not reported";
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(parsed) : value;
}

function executionDate(item: { completed_at?: string | null; started_at?: string | null; created_at?: string | null }) {
  const raw = item.completed_at || item.started_at || item.created_at;
  if (!raw) return Number.NEGATIVE_INFINITY;
  const value = Date.parse(raw);
  return Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;
}

function safeFilename(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9-_]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80) || "ucif-analysis";
}

function downloadFile(filename: string, content: string, contentType: string) {
  const url = URL.createObjectURL(new Blob([content], { type: contentType }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportPredictionCsv(rows: JsonObject[]) {
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  const cell = (value: unknown) => {
    let text = value === null || value === undefined ? "" : typeof value === "string" ? value : JSON.stringify(value);
    // Protect spreadsheet users from formulas while leaving the API response untouched.
    if (/^[\s]*[=+\-@\t\r]/.test(text)) text = `'${text}`;
    return `"${text.replaceAll('"', '""')}"`;
  };
  return [columns.map(cell).join(","), ...rows.map((row) => columns.map((column) => cell(row[column])).join(","))].join("\r\n");
}

function ReportsPageInner() {
  const searchParams = useSearchParams();
  const routeExecutionId = searchParams.get("execution_id");
  const context = useExecutionContext();
  useLatestRunSelection({ disabled: Boolean(routeExecutionId) });
  const executionId = routeExecutionId || context.executionId;
  const workspace = useAnalysisWorkspace(routeExecutionId);
  const history = useExecutionHistory();
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadMessage, setDownloadMessage] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sectorFilter, setSectorFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortOrder, setSortOrder] = useState("newest");
  const payload = object(workspace.payload);
  const dataset = object(payload?.dataset);
  const execution = object(payload?.execution);
  const reportRefs = array(payload?.reports)?.map(object).filter((value): value is JsonObject => Boolean(value)) || [];
  const reportTexts = object(payload?.report_texts) || {};
  const textEntries = Object.entries(reportTexts).filter((entry): entry is [string, string] => typeof entry[1] === "string" && Boolean(entry[1]));
  const rawRows = array(payload?.predictions)?.map(object).filter((value): value is JsonObject => Boolean(value)) || [];
  const hasPredictionRows = Array.isArray(payload?.predictions) && rawRows.length > 0;
  const baseName = safeFilename(typeof dataset?.filename === "string" ? dataset.filename.replace(/\.[^.]+$/, "") : "ucif-analysis");
  const executionSlug = safeFilename(executionId || "execution");
  const filterOptions = useMemo(() => {
    const items = history.data || [];
    return {
      sectors: Array.from(new Set(items.map((item) => item.sector).filter((value): value is string => Boolean(value)))).sort(),
      statuses: Array.from(new Set(items.map((item) => item.status).filter((value): value is NonNullable<typeof value> => Boolean(value)))).sort(),
    };
  }, [history.data]);
  const filteredExecutions = useMemo(() => {
    const items = history.data || [];
    const query = search.trim().toLowerCase();
    return items
      .filter((item) => !query || [item.execution_id, item.filename, item.sector, item.status].some((value) => String(value || "").toLowerCase().includes(query)))
      .filter((item) => sectorFilter === "all" || item.sector === sectorFilter)
      .filter((item) => statusFilter === "all" || item.status === statusFilter)
      .sort((a, b) => sortOrder === "oldest" ? executionDate(a) - executionDate(b) : executionDate(b) - executionDate(a));
  }, [history.data, search, sectorFilter, statusFilter, sortOrder]);

  function runDownload(action: () => void) {
    setDownloadError(null);
    setDownloadMessage(null);
    try { action(); setDownloadMessage("The browser prepared the export. Check its download prompt or download list."); }
    catch { setDownloadError("The browser could not prepare this export. Please try again."); }
  }

  if (!executionId) {
    return <PageShell><div className="mx-auto w-full max-w-6xl space-y-5">
      <ReportHeader />
      {history.isLoading ? <LoadingState label="Loading saved executions…" /> : null}
      {history.error ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : null}
      {!history.isLoading && !history.error && history.data?.length === 0 ? <EmptyState title="No saved executions" description="Reports are associated with a saved execution. Run an analysis to create one, then return here to inspect its reports and exports." action={<Button render={<Link href="/upload" />}>Start an analysis<FileSpreadsheet className="ml-2 h-4 w-4" /></Button>} /> : null}
      {history.data?.length ? <SectionCard title="Execution archive" description="The history API lists executions. Report references and report text are fetched after you choose a run." action={<DataSourceBadge kind="historical" label={`${history.data.length} executions`} />}>
        <div className="mb-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-[minmax(220px,1fr)_repeat(3,minmax(140px,180px))]">
          <label><span className="sr-only">Search executions</span><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search ID, dataset, sector, or status" /></label>
          <label className="sr-only" htmlFor="report-sector-filter">Filter executions by sector</label>
          <Select value={sectorFilter} onValueChange={(value) => value && setSectorFilter(value)}><SelectTrigger id="report-sector-filter" className="w-full"><SelectValue placeholder="All sectors" /></SelectTrigger><SelectContent><SelectItem value="all">All sectors</SelectItem>{filterOptions.sectors.map((sector) => <SelectItem key={sector} value={sector}>{sectorLabel(sector)}</SelectItem>)}</SelectContent></Select>
          <label className="sr-only" htmlFor="report-status-filter">Filter executions by status</label>
          <Select value={statusFilter} onValueChange={(value) => value && setStatusFilter(value)}><SelectTrigger id="report-status-filter" className="w-full"><SelectValue placeholder="All statuses" /></SelectTrigger><SelectContent><SelectItem value="all">All statuses</SelectItem>{filterOptions.statuses.map((status) => <SelectItem key={status} value={status}>{status}</SelectItem>)}</SelectContent></Select>
          <label className="sr-only" htmlFor="report-sort-order">Sort executions</label>
          <Select value={sortOrder} onValueChange={(value) => value && setSortOrder(value)}><SelectTrigger id="report-sort-order" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="newest">Newest first</SelectItem><SelectItem value="oldest">Oldest first</SelectItem></SelectContent></Select>
        </div>
        {filteredExecutions.length ? <ul className="divide-y divide-border">{filteredExecutions.map((item) => <li key={item.execution_id} className="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0 last:pb-0">
          <div className="min-w-0"><p className="truncate font-mono text-xs text-muted-foreground">{item.execution_id}</p><p className="mt-1 truncate font-medium">{item.filename || "Dataset name not reported"}</p><p className="mt-1 text-xs text-muted-foreground">{item.sector ? sectorLabel(item.sector) : "Sector not reported"} · {item.status || "Status not reported"} · {timestamp(item.completed_at || item.started_at || item.created_at)}</p></div>
          <Button variant="outline" size="sm" render={<Link href={`/reports?execution_id=${encodeURIComponent(item.execution_id)}`} />}>Open execution report<ArrowRight className="ml-2 h-4 w-4" /></Button>
        </li>)}</ul> : <EmptyState title="No matching executions" description="Adjust the search or filters to see executions returned by the history API." />}
      </SectionCard> : null}
    </div></PageShell>;
  }

  if (workspace.isLoading && !payload) return <PageShell><LoadingState label={`Loading reports for ${executionId}…`} /></PageShell>;
  if (workspace.error) return <PageShell><div className="mx-auto w-full max-w-6xl space-y-4"><ReportHeader /><ErrorBanner error={workspace.error} onRetry={() => workspace.refetch()} /><p className="break-all font-mono text-xs text-muted-foreground">Execution ID · {executionId}</p><Button variant="outline" render={<Link href="/reports" onClick={() => context.clearExecutionContext()} />}>Choose another execution</Button></div></PageShell>;
  if (!payload) return <PageShell><EmptyState title="Report data unavailable" description="No execution detail payload was returned for this execution." action={<Button variant="outline" render={<Link href="/reports" onClick={() => context.clearExecutionContext()} />}>Choose another execution</Button>} /></PageShell>;

  const prediction = object(payload.prediction);
  const decision = object(payload.decision);
  const explanation = object(payload.prediction_explanation);
  const metadata = object(payload.metadata);
  const contractRuntime = /contract/i.test(`${display(metadata?.framework_version)} ${display(prediction?.prediction_model)}`);
  const riskDistribution = object(prediction?.risk_distribution);
  const riskCounts = Object.entries(riskDistribution || {}).filter((entry): entry is [string, number] => typeof entry[1] === "number" && Number.isFinite(entry[1]));
  const summaryFields = [
    { label: "Prediction rows", value: prediction?.rows },
    { label: "Predicted churners", value: prediction?.predicted_churners },
    { label: "Average probability", value: prediction?.average_probability },
    { label: "Prediction model", value: prediction?.prediction_model },
  ].filter((field) => field.value !== undefined && field.value !== null && field.value !== "");
  const datasetFields = [
    { label: "Dataset rows", value: dataset?.rows },
    { label: "Dataset columns", value: dataset?.columns },
    { label: "Prediction mode", value: dataset?.prediction_mode },
  ].filter((field) => field.value !== undefined && field.value !== null && field.value !== "");
  const decisionFields = [
    { label: "Decision readiness", value: decision?.decision_readiness },
    { label: "Risk level", value: decision?.risk_level },
    { label: "Recommended action", value: decision?.recommended_action },
    { label: "Evidence strength", value: decision?.evidence_strength },
  ].filter((field) => field.value !== undefined && field.value !== null && field.value !== "");

  return <PageShell><div className="report-print mx-auto w-full max-w-6xl space-y-5 print:max-w-none print:gap-3">
    <div className="flex flex-wrap items-start justify-between gap-3 print:hidden"><div className="min-w-0 flex-1"><ReportHeader /></div><Button type="button" variant="outline" onClick={() => window.print()}><Printer className="mr-2 h-4 w-4" />Print / save report</Button></div>
    <div className="hidden print:block"><ReportHeader /></div>
    <SectionCard title="Selected execution" description="Report and export availability is scoped to this execution." action={<DataSourceBadge kind="available" label="Execution detail API" />} className="print:break-inside-avoid print:shadow-none">
      <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Meta label="Execution ID" value={executionId} mono /><Meta label="Dataset" value={typeof dataset?.filename === "string" ? dataset.filename.split(/[\\/]/).filter(Boolean).at(-1) || dataset.filename : "Not reported"} /><Meta label="Sector" value={typeof dataset?.sector === "string" ? sectorLabel(dataset.sector) : "Not reported"} /><Meta label="Completed" value={timestamp(execution?.completed_at)} /></dl>
      {contractRuntime ? <div className="mt-4 flex flex-wrap items-center gap-2"><DataSourceBadge kind="unverified" label="Contract runtime response" /><p className="text-xs leading-5 text-muted-foreground">Values are returned contract-runtime outputs; they do not establish validated production model performance or probability calibration.</p></div> : null}
      <div className="mt-4 flex flex-wrap gap-2 print:hidden"><Button variant="outline" size="sm" render={<Link href={`/workspace?execution_id=${encodeURIComponent(executionId)}&tab=reports`} />}>Open workspace reports</Button><Button variant="ghost" size="sm" render={<Link href={`/workspace?execution_id=${encodeURIComponent(executionId)}&tab=business`} />}>Business intelligence</Button><Button variant="ghost" size="sm" render={<Link href="/reports" onClick={() => context.clearExecutionContext()} />}>Choose another execution</Button></div>
    </SectionCard>

    <SectionCard title="Executive brief" description="A print-friendly presentation of fields returned for this execution. UCIF formats the response; it does not add analytical findings." className="print:break-inside-avoid print:shadow-none">
      {datasetFields.length ? <><h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">Dataset overview</h3><dl className="mb-5 grid gap-3 sm:grid-cols-3">{datasetFields.map((field) => <Meta key={field.label} label={field.label} value={display(field.value)} />)}</dl></> : null}
      {summaryFields.length ? <><h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">Prediction output</h3><dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{summaryFields.map((field) => <Meta key={field.label} label={field.label} value={formatBriefValue(field.label, field.value)} />)}</dl></> : <EmptyState title="No prediction summary returned" description="This execution did not include the summary fields used in this brief." />}
      {riskCounts.length ? <div className="mt-5"><h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">Returned risk distribution</h3><div className="overflow-x-auto rounded-lg border border-border"><table className="w-full min-w-[320px] text-left text-sm"><thead className="bg-muted/30 text-xs text-muted-foreground"><tr><th scope="col" className="px-3 py-2 font-medium">Risk category</th><th scope="col" className="px-3 py-2 text-right font-medium">Count returned</th></tr></thead><tbody className="divide-y divide-border">{riskCounts.map(([name, count]) => <tr key={name}><th scope="row" className="px-3 py-2 font-medium">{name}</th><td className="px-3 py-2 text-right tabular-nums">{count.toLocaleString()}</td></tr>)}</tbody></table></div></div> : null}
      {decisionFields.length ? <div className="mt-5"><h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">Business and decision output</h3><dl className="grid gap-3 sm:grid-cols-2">{decisionFields.map((field) => <Meta key={field.label} label={field.label} value={display(field.value)} />)}</dl></div> : null}
      {explanation && [explanation.headline, explanation.reason_text, explanation.recommendation_text].some((value) => typeof value === "string" && value.trim()) ? <div className="mt-5 rounded-lg border border-border bg-muted/10 p-4"><h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">Returned analytical narrative</h3>{typeof explanation.headline === "string" && explanation.headline ? <p className="mt-3 text-base font-semibold">{explanation.headline}</p> : null}{typeof explanation.reason_text === "string" && explanation.reason_text ? <p className="mt-2 text-sm leading-6">{explanation.reason_text}</p> : null}{typeof explanation.recommendation_text === "string" && explanation.recommendation_text ? <p className="mt-2 text-sm leading-6 text-muted-foreground">{explanation.recommendation_text}</p> : null}</div> : null}
      {Array.isArray(payload.warnings) ? <div className="mt-5 rounded-lg border border-border bg-muted/10 p-4"><h3 className="text-sm font-semibold">Execution limitations and warnings</h3>{payload.warnings.length ? <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">{payload.warnings.map((warning, index) => <li key={`${display(warning)}-${index}`}>{display(warning)}</li>)}</ul> : <p className="mt-2 text-sm text-muted-foreground">The execution returned no warnings.</p>}</div> : null}
      <p className="mt-4 text-xs leading-5 text-muted-foreground">All values above are scoped to this execution response. They do not establish model validation, causality, or measured retention outcomes.</p>
    </SectionCard>

    <SectionCard title="Available exports" description="Exports are generated only from the selected execution's returned API data." className="print:hidden">
      {downloadError ? <div role="alert" className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{downloadError}</div> : null}
      {downloadMessage ? <div role="status" aria-live="polite" className="mb-4 rounded-lg border border-success/30 bg-success/5 p-3 text-sm text-foreground">{downloadMessage}</div> : null}
      <div className="grid gap-3 md:grid-cols-3">
        <ExportCard title="Execution detail" format="JSON" description="Raw execution payload returned by the detail API." available={Boolean(payload)} onDownload={() => runDownload(() => downloadFile(`${baseName}-${executionSlug}.json`, JSON.stringify(payload, null, 2), "application/json;charset=utf-8"))} icon={<FileJson2 className="h-5 w-5" />} />
        <ExportCard title="Prediction records" format="CSV" description="Returned record-level rows only. Spreadsheet formula prefixes are neutralized in the exported copy." available={hasPredictionRows} unavailableText="No record-level prediction rows were returned for this execution." onDownload={() => runDownload(() => downloadFile(`${baseName}-${executionSlug}-predictions.csv`, exportPredictionCsv(rawRows), "text/csv;charset=utf-8"))} icon={<FileSpreadsheet className="h-5 w-5" />} />
        <div className="rounded-xl border border-dashed border-border bg-muted/10 p-4"><p className="text-sm font-semibold">PDF / Excel</p><p className="mt-2 text-xs leading-5 text-muted-foreground">Not available: the backend exposes no PDF or spreadsheet report generator or file download endpoint.</p></div>
      </div>
    </SectionCard>

    <SectionCard title="Returned reports" description="References and report text are taken from this execution detail response. No file URL is inferred from reference metadata." action={<DataSourceBadge kind="historical" label="Selected execution" />} className="print:break-inside-avoid print:shadow-none">
      {reportRefs.length ? <div className="mb-5 space-y-3">{reportRefs.map((report, index) => <article key={String(report.id ?? index)} className="grid gap-2 rounded-lg border border-border bg-background p-4 sm:grid-cols-[minmax(0,1fr)_auto]">
        <div className="min-w-0"><h3 className="font-semibold">{display(report.title)}</h3><p className="mt-1 text-xs text-muted-foreground">Type: {display(report.type)} · Availability: reference metadata</p>{typeof report.location === "string" ? <p className="mt-1 break-all font-mono text-xs text-muted-foreground">Location metadata: {report.location}</p> : null}</div><p className="text-xs text-muted-foreground">Timestamp: {display(report.created_at)}</p>
      </article>)}<p className="text-xs leading-5 text-muted-foreground">Reference locations are not treated as download URLs. No report-file endpoint is available.</p></div> : null}
      {textEntries.length ? <div className="space-y-3">{textEntries.map(([name, text]) => <details key={name} className="group rounded-lg border border-border bg-background">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3"><span className="flex items-center gap-2 font-medium"><FileText className="h-4 w-4 text-primary" />{name.replaceAll("_", " ")}</span><span className="text-xs text-muted-foreground">Preview returned text</span></summary>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border p-3 print:hidden"><p className="text-xs text-muted-foreground">Backend-generated text · TXT export</p><Button type="button" size="sm" variant="outline" onClick={() => runDownload(() => downloadFile(`${baseName}-${executionSlug}-${safeFilename(name)}.txt`, text, "text/plain;charset=utf-8"))}><Download className="mr-2 h-4 w-4" />Download TXT</Button></div>
        <pre className="max-h-[560px] overflow-auto whitespace-pre-wrap break-words border-t border-border bg-muted/10 p-4 font-mono text-xs leading-5">{text}</pre>
      </details>)}</div> : null}
      {!reportRefs.length && !textEntries.length ? <EmptyState title="No reports returned" description="This execution has no report references or report text. The JSON execution export remains available; prediction CSV is available only when record-level rows were returned." /> : null}
    </SectionCard>
  </div></PageShell>;
}

function ReportHeader() {
  return <header className="premium-panel flex flex-wrap items-start justify-between gap-4 p-6"><div><p className="text-xs font-semibold uppercase tracking-widest text-primary">Report Center</p><h1 className="mt-2 text-2xl font-semibold tracking-tight">Traceable analysis reports and exports</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Inspect reports generated for an actual execution and export the data the framework returned.</p></div><FileText className="h-6 w-6 text-primary" /></header>;
}

function Meta({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="min-w-0 rounded-lg border border-border bg-muted/10 p-3"><dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</dt><dd className={`mt-1 break-all text-sm ${mono ? "font-mono text-xs" : "font-medium"}`}>{value}</dd></div>;
}

function ExportCard({ title, format, description, available, unavailableText, onDownload, icon }: { title: string; format: string; description: string; available: boolean; unavailableText?: string; onDownload: () => void; icon: React.ReactNode }) {
  return <div className="flex min-h-48 flex-col rounded-xl border border-border bg-card p-4"><div className="flex items-center justify-between"><span className="text-primary">{icon}</span><DataSourceBadge kind={available ? "available" : "unavailable"} label={available ? `${format} available` : "Unavailable"} /></div><h3 className="mt-4 text-sm font-semibold">{title}</h3><p className="mt-2 flex-1 text-xs leading-5 text-muted-foreground">{available ? description : unavailableText}</p><Button className="mt-4 w-full" variant="outline" size="sm" onClick={onDownload} disabled={!available}><Download className="mr-2 h-4 w-4" />Download {format}</Button></div>;
}

export default function ReportsPage() {
  return <Suspense fallback={<PageShell><LoadingState label="Loading Report Center…" /></PageShell>}><ReportsPageInner /></Suspense>;
}
