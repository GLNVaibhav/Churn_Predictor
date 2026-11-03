"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "motion/react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  FileBarChart2,
  FileText,
  Gauge,
  HeartPulse,
  Landmark,
  Layers3,
  Microscope,
  Phone,
  ShoppingBag,
  Upload,
} from "lucide-react";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { DataSourceBadge, type DataSourceKind } from "@/components/shared/data-source-badge";
import { ErrorBanner, EmptyState, LoadingState } from "@/components/shared/query-states";
import { Reveal } from "@/components/motion/reveal";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { apiRequest } from "@/lib/api/client";
import { getExecutionReports, type ReportsResponse } from "@/lib/api/reports";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { useLatestRunSelection } from "@/lib/hooks/use-latest-run-selection";
import { useExecutionContext } from "@/lib/context/execution-context";
import type { ExecutionSummaryResponse } from "@/lib/api/executions";
import { sectorLabel } from "@/lib/constants/sectors";
import { cn } from "@/lib/utils";
import { ExecutionAnalytics, SectorExecutionChart } from "@/components/dashboard/operational-analytics";

type HealthResponse = { status: string; timestamp?: string; framework_version?: string };
type FrameworkResponse = {
  framework_version?: string;
  supported_sectors?: string[];
  available_modules?: string[];
};

const sectors = [
  { id: "telecom", label: "Telecom", Icon: Phone },
  { id: "banking", label: "Banking", Icon: Landmark },
  { id: "ecommerce", label: "E-commerce", Icon: ShoppingBag },
  { id: "healthcare", label: "Healthcare", Icon: HeartPulse },
] as const;

const quickActions = [
  { href: "/upload", label: "Start an analysis", detail: "Upload and inspect a customer dataset", Icon: Upload },
  { href: "/predictions", label: "Prediction review", detail: "Open prediction evidence for a run", Icon: Activity },
  { href: "/reports", label: "Reports", detail: "Review reports attached to an analysis", Icon: FileBarChart2 },
  { href: "/decision-intelligence", label: "Decision intelligence", detail: "Explore decision evidence and actions", Icon: Microscope },
] as const;

function normalizedSector(value?: string | null) {
  return value?.trim().toLowerCase().replace(/[\s-]+/g, "") || "";
}

function normalizedStatus(value?: string | null) {
  return value?.trim().toUpperCase() || "UNKNOWN";
}

function isSuccessful(status?: string | null) {
  return ["SUCCEEDED", "SUCCESS", "COMPLETE", "COMPLETED"].includes(normalizedStatus(status));
}

function displayDate(value?: string | null) {
  if (!value) return "Date not reported";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "Date not reported";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function platformStatus(
  health: { data?: HealthResponse; isPending: boolean; isError: boolean },
  framework: { data?: FrameworkResponse; isPending: boolean; isError: boolean },
): { kind: DataSourceKind; label: string; detail: string } {
  if (health.isPending || framework.isPending) {
    return { kind: "loading", label: "Checking", detail: "Verifying API and framework metadata." };
  }
  if (health.data?.status?.toUpperCase() === "OK" && framework.data) {
    return { kind: "available", label: "Available", detail: "Health check and framework metadata responded." };
  }
  if (health.isError && framework.isError) {
    return { kind: "failed", label: "Requests failed", detail: "Health and framework metadata requests failed." };
  }
  if ((health.data?.status?.toUpperCase() === "OK" && framework.isError) || (health.isError && framework.data)) {
    return { kind: "degraded", label: "Degraded", detail: "One platform endpoint responded; another could not be verified." };
  }
  if (health.isError || framework.isError) {
    return { kind: "failed", label: "Request failed", detail: "Platform status could not be verified because an API request failed." };
  }
  if (health.data && health.data.status?.toUpperCase() !== "OK") {
    return { kind: "unavailable", label: "Unavailable", detail: "The health endpoint returned a non-OK status." };
  }
  return { kind: "unknown", label: "Unknown", detail: "The current environment did not return enough information to verify platform status." };
}

function RunStatus({ status }: { status?: string | null }) {
  const value = normalizedStatus(status);
  const presentation: Record<string, { label: string; className: string }> = {
    SUCCEEDED: { label: "Succeeded", className: "border-success/30 bg-success/10 text-success" },
    SUCCESS: { label: "Succeeded", className: "border-success/30 bg-success/10 text-success" },
    COMPLETE: { label: "Complete", className: "border-success/30 bg-success/10 text-success" },
    COMPLETED: { label: "Complete", className: "border-success/30 bg-success/10 text-success" },
    FAILED: { label: "Failed", className: "border-destructive/30 bg-destructive/10 text-destructive" },
    RUNNING: { label: "Running", className: "border-info/30 bg-info/10 text-info" },
    PENDING: { label: "Pending", className: "border-warning/30 bg-warning/10 text-warning" },
    CANCELLED: { label: "Cancelled", className: "border-border bg-muted text-muted-foreground" },
  };
  const state = presentation[value];
  return (
    <Badge variant="outline" className={cn("whitespace-nowrap", state?.className || "border-border bg-muted text-muted-foreground")}>
      {state?.label || (value === "UNKNOWN" ? "Status not reported" : value)}
    </Badge>
  );
}

function PlatformStatusCard({
  overall,
  health,
  framework,
  latestRun,
  historyPending,
  historyError,
}: {
  overall: ReturnType<typeof platformStatus>;
  health: HealthResponse | undefined;
  framework: FrameworkResponse | undefined;
  latestRun?: ExecutionSummaryResponse;
  historyPending: boolean;
  historyError: boolean;
}) {
  return (
    <div className="rounded-xl border border-sidebar-border bg-sidebar-accent/55 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/60">Platform status</p>
          <p className="mt-1 text-lg font-semibold text-sidebar-foreground">Service availability</p>
        </div>
        <DataSourceBadge kind={overall.kind} label={overall.label} />
      </div>
      <p className="mt-2 text-xs leading-5 text-sidebar-foreground/65">{overall.detail}</p>
      <div className="mt-4 grid grid-cols-1 gap-2 border-t border-sidebar-border pt-4 text-xs sm:grid-cols-3">
        <div>
          <p className="text-sidebar-foreground/55">API health</p>
          <p className="mt-1 font-medium text-sidebar-foreground">
            {health?.status?.toUpperCase() === "OK" ? "OK" : health ? health.status : "Not verified"}
          </p>
        </div>
        <div>
          <p className="text-sidebar-foreground/55">Framework version</p>
          <p className="mt-1 truncate font-medium text-sidebar-foreground">{framework?.framework_version || "Not reported"}</p>
        </div>
        <div>
          <p className="text-sidebar-foreground/55">Latest execution</p>
          <p className="mt-1 font-medium text-sidebar-foreground">{latestRun ? normalizedStatus(latestRun.status) : historyPending ? "Checking history" : historyError ? "History unavailable" : "No execution recorded"}</p>
        </div>
      </div>
      {health?.timestamp ? <p className="mt-3 text-[10px] text-sidebar-foreground/50">Health response: {displayDate(health.timestamp)}</p> : null}
    </div>
  );
}

function MetricSkeletons() {
  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border/80 bg-border sm:grid-cols-3 xl:grid-cols-5" aria-label="Loading intelligence overview">
      {Array.from({ length: 5 }, (_, index) => <Skeleton key={index} className="h-[132px] rounded-none" />)}
    </div>
  );
}

function OverviewMetric({
  label,
  value,
  description,
  icon: Icon,
}: {
  label: string;
  value: string;
  description: string;
  icon: typeof Layers3;
}) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      whileHover={reduceMotion ? undefined : { y: -2 }}
      transition={{ duration: 0.16 }}
      className="min-w-0 bg-card p-4 transition-colors hover:bg-muted/20 sm:p-5"
    >
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-[10px] font-semibold uppercase tracking-[.12em] text-muted-foreground">{label}</p>
        <Icon className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
      </div>
      <p className="mt-4 truncate text-2xl font-semibold tracking-tight tabular-nums sm:text-3xl">{value}</p>
      <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-muted-foreground">{description}</p>
    </motion.div>
  );
}

function ExecutionActivity({
  executions,
  onOpen,
}: {
  executions: ExecutionSummaryResponse[];
  onOpen: (execution: ExecutionSummaryResponse) => void;
}) {
  if (!executions.length) {
    return (
      <EmptyState
        title="No executions recorded"
        description="Completed and in-progress analyses will appear here after a dataset is submitted."
        action={<Link href="/upload" className={buttonVariants({ size: "sm" })}>Start an analysis</Link>}
      />
    );
  }

  return (
    <>
      <div className="space-y-3 md:hidden">
        {executions.map((execution, index) => (
          <article key={`${execution.execution_id || execution.created_at || "execution"}-${index}`} className="rounded-lg border border-border bg-background p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-mono text-xs font-medium">{execution.execution_id || "ID not reported"}</p>
                <p className="mt-1 truncate text-sm font-medium">{execution.filename || "Dataset name not reported"}</p>
              </div>
              <RunStatus status={execution.status} />
            </div>
            <div className="mt-3 flex items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>{sectorLabel(execution.sector)}</span>
              <span>{displayDate(execution.created_at || execution.started_at)}</span>
            </div>
            <Button variant="ghost" size="sm" className="mt-2 w-full" disabled={!execution.execution_id} onClick={() => onOpen(execution)}>
              Open execution <ArrowRight className="ml-2 h-3.5 w-3.5" />
            </Button>
          </article>
        ))}
      </div>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-border text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            <tr>
              <th className="px-3 py-3">Execution</th>
              <th className="px-3 py-3">Dataset</th>
              <th className="px-3 py-3">Sector</th>
              <th className="px-3 py-3">Created</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3 text-right"> </th>
            </tr>
          </thead>
          <tbody>
            {executions.map((execution, index) => (
              <tr key={`${execution.execution_id || execution.created_at || "execution"}-${index}`} className="border-b border-border/60 last:border-0 hover:bg-muted/25">
                <td className="max-w-36 truncate px-3 py-3 font-mono text-xs">{execution.execution_id || "ID not reported"}</td>
                <td className="max-w-48 truncate px-3 py-3">{execution.filename || "Dataset name not reported"}</td>
                <td className="px-3 py-3">{sectorLabel(execution.sector)}</td>
                <td className="whitespace-nowrap px-3 py-3 text-xs text-muted-foreground">{displayDate(execution.created_at || execution.started_at)}</td>
                <td className="px-3 py-3"><RunStatus status={execution.status} /></td>
                <td className="px-3 py-3 text-right">
                  <Button variant="ghost" size="sm" disabled={!execution.execution_id} onClick={() => onOpen(execution)} aria-label={`Open execution ${execution.execution_id || "not reported"}`}>
                    Open <ArrowRight className="ml-1 h-3.5 w-3.5" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const context = useExecutionContext();
  useLatestRunSelection({ preferLatest: true });
  const history = useExecutionHistory();
  const health = useQuery({
    queryKey: ["api-health"],
    queryFn: ({ signal }) => apiRequest<HealthResponse>("/api/v1/health", {}, signal),
    refetchInterval: 15_000,
    retry: 1,
  });
  const framework = useQuery({
    queryKey: ["framework"],
    queryFn: ({ signal }) => apiRequest<FrameworkResponse>("/api/v1/framework", {}, signal),
  });

  const executions = useMemo(() => history.data || [], [history.data]);
  const latestExecution = executions[0];
  const latestSuccessfulExecution = executions.find((execution) => isSuccessful(execution.status) && Boolean(execution.execution_id));
  const reports = useQuery<ReportsResponse>({
    queryKey: ["reports", latestSuccessfulExecution?.execution_id],
    enabled: Boolean(latestSuccessfulExecution?.execution_id),
    queryFn: ({ signal }) => getExecutionReports(latestSuccessfulExecution!.execution_id, signal),
  });
  const reportMetric = latestSuccessfulExecution
    ? reports.data
      ? reports.data.reports.length.toLocaleString()
      : reports.isError
        ? "Unavailable"
        : reports.isPending
          ? "Loading"
          : "0"
    : "—";
  const reportMetricDescription = latestSuccessfulExecution
    ? reports.data
      ? `Attached to ${latestSuccessfulExecution.execution_id}`
      : reports.isError
        ? "The report request failed"
        : reports.isPending
          ? "Checking the latest successful run"
          : "No report references returned"
    : "No completed execution to query";

  const counts = useMemo(() => ({
    total: executions.length,
    successful: executions.filter((execution) => isSuccessful(execution.status)).length,
    active: executions.filter((execution) => ["PENDING", "RUNNING"].includes(normalizedStatus(execution.status))).length,
    failed: executions.filter((execution) => normalizedStatus(execution.status) === "FAILED").length,
  }), [executions]);

  const status = platformStatus(health, framework);

  function openExecution(execution: ExecutionSummaryResponse, destination = "/workspace") {
    context.setExecutionContext({
      executionId: execution.execution_id || null,
      uploadId: null,
      filename: execution.filename || null,
      sector: execution.sector || null,
      status: execution.status || null,
    });
    const href = execution.execution_id && (destination === "/workspace" || destination === "/reports")
      ? `${destination}?execution_id=${encodeURIComponent(execution.execution_id)}`
      : destination;
    router.push(href);
  }

  return (
    <PageShell className="gap-6 lg:gap-7">
      <Reveal>
        <section className="mission-control-hero overflow-hidden rounded-2xl border border-sidebar-border p-5 text-sidebar-foreground shadow-[var(--shadow-card)] sm:p-7 lg:p-8" aria-labelledby="mission-control-title">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.78fr)] xl:items-center">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-sidebar-primary">Universal Churn Intelligence</span>
                {context.status === "demo" ? <DataSourceBadge kind="demonstration" label="Demo context selected" /> : null}
              </div>
              <h1 id="mission-control-title" className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Mission Control</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-sidebar-foreground/70 sm:text-base">
                From heterogeneous customer data to actionable business intelligence. Monitor verified framework activity and move into the next analysis.
              </p>
              {context.status === "demo" ? <p className="mt-2 text-xs text-sidebar-foreground/55">The selected demo applies to the workspace preview. The activity and platform information below remain API-backed.</p> : null}
              <div className="mt-5 flex flex-wrap gap-2">
                <Link href="/upload" className={buttonVariants({ size: "lg" })}>
                  <Upload className="mr-2 h-4 w-4" /> New Analysis
                </Link>
                <Link href="/analyses" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "border-sidebar-border bg-sidebar-accent/55 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground")}>
                  View execution history <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
                {latestExecution?.execution_id ? (
                  <Button variant="outline" size="lg" className="border-sidebar-border bg-sidebar-accent/55 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground" onClick={() => openExecution(latestExecution)}>
                    Open latest workspace <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                ) : null}
              </div>
            </div>
            <PlatformStatusCard overall={status} health={health.data} framework={framework.data} latestRun={latestExecution} historyPending={history.isPending} historyError={history.isError} />
          </div>
        </section>
      </Reveal>

      <Reveal delay={0.04}>
        <section aria-labelledby="overview-title" className="space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">Operational overview</p>
              <h2 id="overview-title" className="mt-1 text-lg font-semibold tracking-tight">Intelligence overview</h2>
            </div>
            {history.data ? <DataSourceBadge kind="historical" label="Execution history API" /> : null}
          </div>
          {history.isPending ? <MetricSkeletons /> : history.isError ? (
            <ErrorBanner error={history.error} onRetry={() => history.refetch()} />
          ) : (
            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border/80 bg-border shadow-[var(--shadow-card)] sm:grid-cols-3 xl:grid-cols-5">
              <OverviewMetric label="Execution records" value={counts.total.toLocaleString()} icon={Layers3} description="Records returned by execution history" />
              <OverviewMetric label="Successful runs" value={counts.successful.toLocaleString()} icon={CheckCircle2} description="Succeeded or success status" />
              <OverviewMetric label="In progress" value={counts.active.toLocaleString()} icon={Activity} description="Pending or running status" />
              <OverviewMetric label="Failed runs" value={counts.failed.toLocaleString()} icon={Clock3} description="Failed status in execution history" />
              <OverviewMetric label="Reports · latest run" value={reportMetric} icon={FileBarChart2} description={reportMetricDescription} />
            </div>
          )}
        </section>
      </Reveal>

      <Reveal delay={0.055}>
        <section aria-labelledby="analytics-title" className="space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">Execution analytics</p>
              <h2 id="analytics-title" className="mt-1 text-lg font-semibold tracking-tight">Activity and execution status</h2>
            </div>
            <DataSourceBadge kind="historical" label="Derived from execution history" />
          </div>
          {history.isPending ? (
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(280px,.85fr)]"><Skeleton className="h-[300px] rounded-2xl" /><Skeleton className="h-[300px] rounded-2xl" /></div>
          ) : history.isError ? (
            <ErrorBanner error={history.error} onRetry={() => history.refetch()} />
          ) : (
            <ExecutionAnalytics executions={executions} />
          )}
        </section>
      </Reveal>

      <Reveal delay={0.07}>
        <section aria-labelledby="sector-title" className="space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">Domain coverage</p>
              <h2 id="sector-title" className="mt-1 text-lg font-semibold tracking-tight">Sector activity and framework support</h2>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {framework.data?.supported_sectors ? <DataSourceBadge kind="live" label={`${framework.data.supported_sectors.length} sectors listed by framework`} /> : <DataSourceBadge kind={framework.isPending ? "loading" : framework.isError ? "failed" : "unknown"} label={framework.isPending ? "Checking framework" : framework.isError ? "Framework request failed" : "Sector list not reported"} />}
            </div>
          </div>
          <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(280px,.65fr)]">
            <SectionCard title="Execution records by sector" description="Counts grouped from the sector values in returned execution history" action={<BarChart3 className="h-4 w-4 text-primary" aria-hidden="true" />}>
              {history.isPending ? <Skeleton className="h-[230px] rounded-xl" /> : history.isError ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : <SectorExecutionChart executions={executions} />}
            </SectionCard>
            <SectionCard title="Framework-supported domains" description="Listed by the framework metadata endpoint">
              {framework.isPending ? <div className="space-y-2">{Array.from({ length: 3 }, (_, index) => <Skeleton key={index} className="h-12 rounded-lg" />)}</div> : framework.isError ? <ErrorBanner error={framework.error} onRetry={() => framework.refetch()} /> : framework.data?.supported_sectors?.length ? (
                <ul className="space-y-2">
                  {framework.data.supported_sectors.map((sector) => {
                    const known = sectors.find((item) => normalizedSector(item.id) === normalizedSector(sector));
                    const Icon = known?.Icon || Layers3;
                    return <li key={sector} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-3">
                      <span className="flex min-w-0 items-center gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/8 text-primary"><Icon className="h-4 w-4" aria-hidden="true" /></span><span className="truncate text-sm font-medium">{sectorLabel(sector)}</span></span>
                      <Badge variant="outline" className="border-success/30 bg-success/10 text-success">Listed</Badge>
                    </li>;
                  })}
                </ul>
              ) : <div className="rounded-xl border border-dashed border-border bg-muted/15 p-5 text-xs leading-5 text-muted-foreground">Framework metadata did not report a supported-sector list.</div>}
            </SectionCard>
          </div>
        </section>
      </Reveal>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(300px,0.6fr)]">
        <Reveal delay={0.08}>
          <SectionCard
            title="Analysis activity"
            description="Recent executions returned by the backend, newest first"
            action={history.data ? <DataSourceBadge kind="historical" label="API records" /> : undefined}
            contentClassName="pt-4"
          >
            {history.isPending ? <LoadingState label="Loading execution history..." /> : history.isError ? (
              <ErrorBanner error={history.error} onRetry={() => history.refetch()} />
            ) : (
              <ExecutionActivity executions={executions.slice(0, 6)} onOpen={(execution) => openExecution(execution)} />
            )}
          </SectionCard>
        </Reveal>

        <Reveal delay={0.1}>
          <SectionCard title="Model performance" description="Verified evaluation metrics for this project">
            <div className="rounded-xl border border-dashed border-border bg-muted/15 p-5">
              <div className="flex items-center justify-between gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground"><Gauge className="h-5 w-5" /></span>
                <DataSourceBadge kind="unavailable" label="No evaluation endpoint" />
              </div>
              <h3 className="mt-4 text-sm font-semibold">Performance is not reported here</h3>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                Current health, framework, and execution-history responses do not provide verified accuracy, precision, recall, F1, ROC-AUC, or PR-AUC values. Mission Control does not infer or combine model scores.
              </p>
            </div>
          </SectionCard>
        </Reveal>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Reveal delay={0.12}>
          <SectionCard
            title="Recent reports"
            description={latestSuccessfulExecution ? `Reports attached to completed execution ${latestSuccessfulExecution.execution_id}` : "Reports are retrieved from a completed execution"}
            action={reports.data ? <DataSourceBadge kind="historical" label="Execution reports" /> : undefined}
          >
            {history.isPending ? (
              <LoadingState label="Checking for a completed execution..." />
            ) : history.isError ? (
              <ErrorBanner error={history.error} onRetry={() => history.refetch()} />
            ) : !latestSuccessfulExecution ? (
              <EmptyState title="No completed execution" description="A report list is available after an execution succeeds." />
            ) : reports.isPending ? (
              <LoadingState label="Loading reports for the latest completed execution..." />
            ) : reports.isError ? (
              <ErrorBanner error={reports.error} onRetry={() => reports.refetch()} />
            ) : reports.data?.reports.length ? (
              <ul className="space-y-2">
                {reports.data.reports.slice(0, 5).map((report, index) => {
                  const title = String(report.title || report.type || "Report title not reported");
                  return (
                    <li key={String(report.id || `${title}-${index}`)} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <FileText aria-hidden="true" className="h-4 w-4 shrink-0 text-primary" />
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{title}</p>
                          <p className="mt-0.5 text-xs text-muted-foreground">{displayDate(String(report.created_at || ""))}</p>
                        </div>
                      </div>
                      <Button variant="ghost" size="sm" onClick={() => openExecution(latestSuccessfulExecution, "/reports")}>
                        View <ArrowRight className="ml-1 h-3.5 w-3.5" />
                      </Button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <EmptyState title="No reports attached" description="The latest completed execution did not return report references." />
            )}
          </SectionCard>
        </Reveal>

        <Reveal delay={0.14}>
          <SectionCard title="Quick actions" description="Open an existing UCIF workflow">
            <div className="grid gap-2 sm:grid-cols-2">
              {quickActions.map(({ href, label, detail, Icon }) => (
                <Link key={href} href={href} className="group flex min-h-20 items-center gap-3 rounded-lg border border-border bg-background p-3 outline-none transition-colors hover:border-primary/30 hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-card text-primary"><Icon aria-hidden="true" className="h-4 w-4" /></span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">{label}</span>
                    <span className="mt-0.5 block text-xs leading-4 text-muted-foreground">{detail}</span>
                  </span>
                  <ArrowRight aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
                </Link>
              ))}
            </div>
          </SectionCard>
        </Reveal>
      </div>

      {health.error || framework.error ? (
        <div className="grid gap-3 md:grid-cols-2">
          {health.error ? <ErrorBanner error={health.error} onRetry={() => health.refetch()} /> : null}
          {framework.error ? <ErrorBanner error={framework.error} onRetry={() => framework.refetch()} /> : null}
        </div>
      ) : null}
      <div className="sr-only" aria-live="polite">Platform status: {status.label}. API status: {health.data?.status || "unknown"}.</div>
    </PageShell>
  );
}
