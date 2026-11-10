"use client";

import { useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { DataSourceBadge } from "@/components/shared/data-source-badge";
import { WorkspaceSectionView } from "@/components/workspace/workspace-sections";
import { Button } from "@/components/ui/button";
import { useAnalysisWorkspace } from "@/lib/hooks/use-analysis-workspace";
import { useLatestRunSelection } from "@/lib/hooks/use-latest-run-selection";
import { useExecutionPipeline, useExecutionPredictions } from "@/lib/hooks/use-execution";
import { ApiError } from "@/lib/api/client";
import { WORKSPACE_SECTIONS, type WorkspaceSection } from "@/lib/navigation";
import { useExecutionContext } from "@/lib/context/execution-context";
import { demoRunForSector } from "@/components/dashboard/recent-runs-table";
import type { Sector } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ArrowRight, BarChart3, CheckCircle2, Clock3, Database, FileSpreadsheet, RefreshCw, ShieldAlert } from "lucide-react";

const sectors: Sector[] = ["telecom", "banking", "ecommerce", "healthcare"];
const sectorLabel: Record<Sector, string> = {
  telecom: "Telecom",
  banking: "Banking",
  ecommerce: "E-commerce",
  healthcare: "Healthcare",
};

function WorkspacePreview({ activeSector }: { activeSector: Sector }) {
  const run = demoRunForSector(activeSector);
  return (
    <div className="premium-panel overflow-hidden">
      <div className="border-b border-border bg-muted/20 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-xs font-semibold uppercase tracking-widest text-primary">Illustrative workspace preview</p><DataSourceBadge kind="demonstration" label="Demonstration data" /></div>
        <div className="mt-2 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Load a demo run or upload your own CSV.</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              These fixed example values show the workspace layout only. Run an analysis to inspect API-returned execution results.
            </p>
          </div>
          <Link href="/upload">
            <Button>
              <FileSpreadsheet className="mr-2 h-4 w-4" />
              Upload CSV
            </Button>
          </Link>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {sectors.map((sector) => (
            <Link
              key={sector}
              href={`/workspace?demo=${sector}`}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                sector === activeSector ? "border-primary bg-primary/10 text-primary" : "border-border bg-card text-muted-foreground hover:text-foreground",
              )}
            >
              {sectorLabel[sector]}
            </Link>
          ))}
        </div>
      </div>
      <div className="grid gap-0 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="border-b border-border p-5 lg:border-b-0 lg:border-r">
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Demo run</p>
            <p className="mt-2 text-lg font-semibold">{sectorLabel[activeSector]}</p>
            <div className="mt-4 grid gap-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Customers</span>
                <span className="font-semibold tabular-nums">{run.recordCount.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">At risk</span>
                <span className="font-semibold tabular-nums">{run.atRiskRate.toFixed(1)}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Top driver</span>
                <span className="font-medium">{run.topDriver}</span>
              </div>
            </div>
          </div>
          <Link href={`/reports?demo=${activeSector}`}>
            <Button variant="outline" className="mt-3 w-full">
              Preview reports
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
        <div className="p-5">
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: "Prediction", value: `${run.avgRisk.toFixed(1)}%`, Icon: BarChart3 },
              { label: "Evidence", value: run.semanticStatus, Icon: CheckCircle2 },
              { label: "Decision", value: run.avgRisk > 50 ? "Escalate" : "Monitor", Icon: ShieldAlert },
            ].map(({ label, value, Icon }) => (
              <div key={label} className="rounded-lg border border-border bg-background p-4">
                <Icon className="h-4 w-4 text-primary" />
                <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
                <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 overflow-hidden rounded-lg border border-border">
            <div className="grid grid-cols-[1fr_120px_120px] border-b border-border bg-muted/35 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <span>Cohort</span>
              <span>Risk</span>
              <span>Status</span>
            </div>
            {[
              ["Dormant premium customers", run.avgRisk],
              ["Low engagement cohort", Math.max(18, run.avgRisk - 14)],
              ["Recently active customers", Math.max(8, run.avgRisk - 31)],
            ].map(([label, risk]) => (
              <div key={String(label)} className="grid grid-cols-[1fr_120px_120px] items-center border-b border-border/60 px-4 py-3 text-sm last:border-b-0">
                <span className="font-medium">{label}</span>
                <span className="tabular-nums">{Number(risk).toFixed(1)}%</span>
                <span className="w-fit rounded-full border border-red-200 bg-red-50 px-2 py-1 text-xs font-medium text-red-800">At risk</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function WorkspacePageInner() {
  const searchParams = useSearchParams();
  const reduceMotion = useReducedMotion();
  const sectionNavRef = useRef<HTMLDivElement | null>(null);
  const activeSectionRef = useRef<HTMLAnchorElement | null>(null);
  const requestedTab = searchParams.get("tab");
  const tab = WORKSPACE_SECTIONS.some((section) => section.id === requestedTab)
    ? requestedTab as WorkspaceSection
    : "overview";
  const demo = (searchParams.get("demo") as Sector | null) || null;
  const requestedExecutionId = searchParams.get("execution_id");
  const ctx = useExecutionContext();
  useLatestRunSelection({ disabled: Boolean(requestedExecutionId) || Boolean(demo) });
  const selectedExecutionId = requestedExecutionId || ctx.executionId;
  const workspace = useAnalysisWorkspace(selectedExecutionId);
  const payload = workspace.payload as Record<string, unknown> | null;
  const execution = payload?.execution && typeof payload.execution === "object" ? payload.execution as Record<string, unknown> : payload ?? {};
  const dataset = payload?.dataset && typeof payload.dataset === "object" ? payload.dataset as Record<string, unknown> : {};
  const status = String(execution.status ?? payload?.status ?? (ctx.executionId === selectedExecutionId ? ctx.status : "") ?? "").toUpperCase();
  const detailPipeline = payload?.pipeline ?? payload?.pipeline_state;
  const hasDetailPipelineStages = Boolean(
    detailPipeline && typeof detailPipeline === "object" && !Array.isArray(detailPipeline) &&
    Array.isArray((detailPipeline as Record<string, unknown>).stages) &&
    ((detailPipeline as Record<string, unknown>).stages as unknown[]).length > 0
  );
  const shouldLoadPipelineEndpoint = Boolean(selectedExecutionId && workspace.isSuccess && payload && !hasDetailPipelineStages);
  const pipelineQuery = useExecutionPipeline(selectedExecutionId, status, shouldLoadPipelineEndpoint);
  const statusTone = ["SUCCEEDED", "SUCCESS", "COMPLETED", "COMPLETE"].includes(status)
    ? "border-success/35 bg-success/10 text-success"
    : ["FAILED", "CANCELLED"].includes(status)
      ? "border-destructive/35 bg-destructive/10 text-destructive"
      : ["RUNNING", "PENDING", "PARTIAL", "PARTIALLY_COMPLETED", "PARTIALLY_SUCCEEDED", "PARTIAL_SUCCESS"].includes(status)
        ? "border-warning/40 bg-warning/10 text-warning"
        : "border-border bg-muted text-muted-foreground";
  const statusLabel = ["PARTIAL", "PARTIALLY_COMPLETED", "PARTIALLY_SUCCEEDED", "PARTIAL_SUCCESS"].includes(status)
    ? "Partially completed"
    : status ? status.replaceAll("_", " ") : "Unavailable";
  const hasDetailPredictionRows = Array.isArray(payload?.predictions) && payload.predictions.length > 0;
  const executionError = typeof payload?.error === "string" ? payload.error : null;
  const shouldLoadPredictionEndpoint = Boolean(selectedExecutionId && workspace.isSuccess && payload && !hasDetailPredictionRows);
  const predictionQuery = useExecutionPredictions(selectedExecutionId, status, shouldLoadPredictionEndpoint);
  const notFound = workspace.error instanceof ApiError && workspace.error.status === 404;
  const workspaceHref = (section: WorkspaceSection) => {
    const params = new URLSearchParams({ tab: section });
    if (selectedExecutionId) params.set("execution_id", selectedExecutionId);
    return `/workspace?${params.toString()}`;
  };

  useEffect(() => {
    const active = activeSectionRef.current;
    if (!sectionNavRef.current || !active) return;
    active.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest", inline: "center" });
  }, [tab, reduceMotion]);

  return (
    <PageShell>
      {!selectedExecutionId ? (
        demo && sectors.includes(demo) ? <WorkspacePreview activeSector={demo} /> : (
          <EmptyState
            title="No execution selected"
            description="Choose a saved execution or start a new analysis. This workspace shows results returned for the selected run."
            action={<div className="flex flex-wrap justify-center gap-2"><Button render={<Link href="/analyses" />}>Open execution history<ArrowRight className="ml-2 h-4 w-4" /></Button><Button variant="outline" render={<Link href="/upload" />}>Start new analysis</Button></div>}
          />
        )
      ) : null}

      {selectedExecutionId && workspace.error && !notFound ? <ErrorBanner error={workspace.error} onRetry={() => workspace.refetch()} /> : null}
      {selectedExecutionId && workspace.isLoading ? <LoadingState label="Loading the selected execution…" /> : null}
      {selectedExecutionId && notFound ? <EmptyState title="Execution not found" description="The execution ID in this link was not found. Check the ID or open a saved execution from history." action={<div className="flex gap-2"><Button render={<Link href="/analyses" />}>Execution history</Button><Button variant="outline" render={<Link href="/upload" />}>New analysis</Button></div>} /> : null}
      {selectedExecutionId && workspace.isSuccess && !payload ? <EmptyState title="Execution details unavailable" description="The API response did not include an execution detail object for this identifier." /> : null}

      {selectedExecutionId && !workspace.isLoading && !workspace.error && payload ? (
        <>
          <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-[var(--shadow-card)]" aria-labelledby="workspace-title">
            <div className="flex flex-col gap-5 border-b border-border/70 p-5 sm:p-6 xl:flex-row xl:items-end xl:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2"><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-muted-foreground">Execution workspace</p><DataSourceBadge kind="available" label="Selected execution" /></div>
                <h1 id="workspace-title" className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{typeof dataset.filename === "string" ? dataset.filename : "Analysis results"}</h1>
                <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{selectedExecutionId}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${statusTone}`}><span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />{statusLabel}</span>
                <Button variant="outline" size="sm" onClick={() => { void workspace.refetch(); if (shouldLoadPredictionEndpoint) void predictionQuery.refetch(); if (shouldLoadPipelineEndpoint) void pipelineQuery.refetch(); }}><RefreshCw className="mr-2 h-3.5 w-3.5" />Refresh</Button>
                <Button variant="outline" size="sm" render={<Link href="/upload" />}><FileSpreadsheet className="mr-2 h-4 w-4" />New analysis</Button>
              </div>
            </div>
            <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6 sm:p-6">
              <WorkspaceMeta icon={Database} label="Sector" value={typeof dataset.sector === "string" ? sectorLabel[dataset.sector as Sector] || dataset.sector : "Not reported"} />
              <WorkspaceMeta icon={Database} label="Dataset rows" value={dataset.rows === undefined || dataset.rows === null ? "Not reported" : String(dataset.rows)} />
              <WorkspaceMeta icon={Clock3} label="Created" value={dateLabel(execution.created_at)} />
              <WorkspaceMeta icon={Clock3} label="Started" value={dateLabel(execution.started_at)} />
              <WorkspaceMeta icon={Clock3} label="Completed" value={dateLabel(execution.completed_at)} />
              <WorkspaceMeta icon={Clock3} label="Duration" value={execution.execution_time_ms === undefined || execution.execution_time_ms === null ? "Not reported" : `${String(execution.execution_time_ms)} ms`} />
              {typeof execution.progress === "number" && Number.isFinite(execution.progress) ? <WorkspaceMeta icon={Clock3} label="Progress (API value)" value={String(execution.progress)} /> : null}
            </div>
          </section>
          {(["FAILED", "CANCELLED"].includes(status)) ? <ErrorBanner error={new Error(executionError || (status === "CANCELLED" ? "This execution was cancelled." : "Analysis did not complete. Review the dataset and selected sector, then retry."))} /> : null}

          <nav aria-label="Execution analysis sections" className="sticky top-0 z-20 -mx-4 border-y border-border/80 bg-background/95 px-4 py-2 backdrop-blur sm:-mx-5 sm:px-5 lg:-mx-6 lg:px-6">
            <div ref={sectionNavRef} className="flex gap-1 overflow-x-auto">
              {WORKSPACE_SECTIONS.map((section) => (
                <Link
                  key={section.id}
                  ref={tab === section.id ? activeSectionRef : undefined}
                  href={workspaceHref(section.id)}
                  aria-current={tab === section.id ? "page" : undefined}
                  className={cn("relative shrink-0 rounded-lg px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", tab === section.id ? "text-foreground" : "text-muted-foreground hover:text-foreground")}
                >
                  {tab === section.id ? <motion.span layoutId="workspace-active-section" className="absolute inset-0 -z-10 rounded-lg bg-muted" transition={{ duration: reduceMotion ? 0 : 0.18 }} /> : null}
                  <span className="relative">{section.label}</span>
                </Link>
              ))}
            </div>
          </nav>
          <motion.div key={`${selectedExecutionId}:${tab}`} initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduceMotion ? 0 : 0.2 }}>
            <WorkspaceSectionView
              section={tab}
              data={workspace}
              predictionRecords={predictionQuery.data?.predictions}
              predictionLoading={predictionQuery.isLoading}
              predictionError={predictionQuery.error}
              onRetryPredictions={() => void predictionQuery.refetch()}
              pipelineResponse={pipelineQuery.data}
              pipelineLoading={pipelineQuery.isLoading}
              pipelineError={pipelineQuery.error}
              onRetryPipeline={() => void pipelineQuery.refetch()}
            />
          </motion.div>
        </>
      ) : null}
    </PageShell>
  );
}

function WorkspaceMeta({ icon: Icon, label, value }: { icon: typeof Database; label: string; value: string }) {
  return <div className="flex min-w-0 items-center gap-3 rounded-xl border border-border/70 bg-background px-3 py-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground"><Icon className="h-4 w-4" aria-hidden="true" /></span><div className="min-w-0"><p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-1 truncate text-sm font-medium" title={value}>{value}</p></div></div>;
}

function dateLabel(value: unknown) {
  if (typeof value !== "string" || !value) return "Not reported";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
