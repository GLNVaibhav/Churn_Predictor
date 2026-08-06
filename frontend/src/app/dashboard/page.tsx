"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { SectionCard } from "@/components/shared/section-card";
import { RecentRunsEmptyState, RecentRunsTable, demoRunForSector, type DashboardRun } from "@/components/dashboard/recent-runs-table";
import { Button } from "@/components/ui/button";
import { ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { useAnalysisWorkspace } from "@/lib/hooks/use-analysis-workspace";
import { useExecutionContext } from "@/lib/context/execution-context";
import { Sector } from "@/lib/types";
import { ArrowRight, BrainCircuit, Gauge, PlusCircle, UsersRound } from "lucide-react";

function pct(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return n <= 1 ? n * 100 : n;
}

function numberValue(value: unknown) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function topDriverFromPayload(payload: Record<string, unknown> | null | undefined) {
  const reasoning = (payload?.reasoning || payload?.business_reasoning || {}) as Record<string, unknown>;
  const findings = reasoning.dominant_findings as string[] | undefined;
  if (findings?.length) return findings[0];
  const semantic = (payload?.semantic_intelligence || {}) as Record<string, unknown>;
  const meanings = semantic.business_meanings as Record<string, unknown>[] | undefined;
  const firstMeaning = meanings?.find((item) => item.primary_business_concept);
  return String(firstMeaning?.primary_business_concept || "");
}

function DriverBreakdown({ runs }: { runs: DashboardRun[] }) {
  const rows = runs.length
    ? runs.slice(0, 4).map((run) => ({
        label: run.topDriver,
        total: Math.max(1, run.atRiskRate),
        segments: [
          { label: "High risk", value: Math.min(100, run.atRiskRate * 0.52), className: "bg-red-200" },
          { label: "Medium risk", value: Math.min(100, run.atRiskRate * 0.31), className: "bg-amber-200" },
          { label: "Watch", value: Math.min(100, run.atRiskRate * 0.17), className: "bg-sky-200" },
        ],
      }))
    : [
        {
          label: "Awaiting completed run",
          total: 0,
          segments: [
            { label: "High risk", value: 0, className: "bg-red-200" },
            { label: "Medium risk", value: 0, className: "bg-amber-200" },
            { label: "Watch", value: 0, className: "bg-sky-200" },
          ],
        },
      ];

  return (
    <SectionCard title="Top Retention Drivers" description="Risk contribution by cohort segment">
      <div className="space-y-4">
        {rows.map((row) => (
          <div key={row.label} className="grid gap-2 sm:grid-cols-[180px_minmax(0,1fr)_64px] sm:items-center">
            <p className="truncate text-sm font-medium">{row.label}</p>
            <div className="flex h-3 overflow-hidden rounded-full bg-muted">
              {row.segments.map((segment) => (
                <div
                  key={segment.label}
                  className={segment.className}
                  style={{ width: `${Math.max(0, segment.value)}%` }}
                  title={`${segment.label}: ${segment.value.toFixed(1)}%`}
                />
              ))}
            </div>
            <p className="text-right text-sm font-semibold tabular-nums">{row.total.toFixed(1)}%</p>
          </div>
        ))}
        <div className="flex flex-wrap gap-3 border-t border-border pt-3 text-xs text-muted-foreground">
          {[
            ["High risk", "bg-red-200"],
            ["Medium risk", "bg-amber-200"],
            ["Watch", "bg-sky-200"],
          ].map(([label, color]) => (
            <span key={label} className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${color}`} />
              {label}
            </span>
          ))}
        </div>
      </div>
    </SectionCard>
  );
}

function dashboardRunFromExecution(run: Record<string, unknown>): DashboardRun {
  const sector = String(run.sector || "telecom") as Sector;
  const rows = numberValue(run.rows || run.record_count || run.records);
  const churners = numberValue(run.predicted_churners || run.churn_detected || run.churners);
  const avgRisk = pct(run.average_probability || run.avg_risk || run.average_churn_probability);
  return {
    id: String(run.execution_id || run.id || ""),
    sector,
    mode: "Auto",
    routingTier: avgRisk > 70 ? "Red" : avgRisk > 45 ? "Yellow" : "Green",
    recordCount: rows,
    churnDetected: churners,
    avgRisk,
    atRiskRate: rows ? (churners / rows) * 100 : 0,
    topDriver: String(run.top_driver || "Open workspace for driver evidence"),
    semanticStatus: avgRisk > 70 ? "Review" : "Ready",
    submittedAt: String(run.created_at || run.started_at || new Date().toISOString()),
    status:
      run.status === "FAILED"
        ? "failed"
        : run.status === "RUNNING"
          ? "running"
          : "complete",
  };
}

export default function DashboardPage() {
  const context = useExecutionContext();
  const workspace = useAnalysisWorkspace();
  const history = useExecutionHistory();
  const [demoRuns, setDemoRuns] = useState<DashboardRun[]>([]);
  const payload = workspace.payload as Record<string, unknown> | null | undefined;
  const prediction = (payload?.prediction || payload?.predictions || {}) as Record<string, unknown>;
  const dataset = (payload?.dataset || {}) as Record<string, unknown>;

  const historyRuns = useMemo(
    () => ((history.data || []) as unknown as Record<string, unknown>[]).slice(0, 8).map(dashboardRunFromExecution).filter((run) => run.id),
    [history.data],
  );
  const runs = demoRuns.length ? demoRuns : historyRuns;

  const customersAnalyzed = numberValue(prediction.rows || dataset.rows || runs.reduce((sum, run) => sum + run.recordCount, 0));
  const atRisk = numberValue(prediction.predicted_churners || runs.reduce((sum, run) => sum + run.churnDetected, 0));
  const avgRisk = prediction.average_probability !== undefined
    ? pct(prediction.average_probability)
    : runs.length
      ? runs.reduce((sum, run) => sum + run.avgRisk, 0) / runs.length
      : 0;
  const topDriver = payload ? topDriverFromPayload(payload) : runs[0]?.topDriver || "";

  function loadDemo(sector: Sector) {
    const selected = demoRunForSector(sector);
    setDemoRuns([selected]);
    context.setExecutionContext({ executionId: selected.id, sector: selected.sector, status: selected.status });
  }

  return (
    <PageShell>
      <div className="premium-panel p-6">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">Retention dashboard</p>
            <h2 className="mt-2 max-w-3xl text-2xl font-semibold tracking-tight text-foreground">
              Customer churn risk, semantic readiness, and recent analysis activity.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Monitor outcomes from your latest churn runs. Use the New button or command menu to upload a dataset.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/upload">
              <Button>
                <PlusCircle className="mr-2 h-4 w-4" />
                New Run
              </Button>
            </Link>
            {context.executionId ? (
              <Link href="/workspace">
                <Button variant="outline">
                  Open Workspace
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            ) : null}
          </div>
        </div>
      </div>

      {workspace.error ? <ErrorBanner error={workspace.error} onRetry={() => workspace.refetch()} /> : null}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Customers Analyzed" value={customersAnalyzed.toLocaleString()} icon={UsersRound} description="Across selected run context" />
        <MetricCard label="At-risk Customers" value={atRisk.toLocaleString()} icon={BrainCircuit} description={`${customersAnalyzed ? ((atRisk / customersAnalyzed) * 100).toFixed(1) : "0.0"}% of analyzed customers`} />
        <MetricCard label="Average Risk" value={`${avgRisk.toFixed(1)}%`} icon={Gauge} description="Mean churn probability" />
        {topDriver ? (
          <MetricCard label="Top Driver" value={topDriver} icon={ArrowRight} description="Primary business signal" />
        ) : (
          <div className="rounded-lg bg-card/95 p-4 text-sm text-card-foreground ring-1 ring-border/80">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Top Driver</p>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="mt-3 text-base font-semibold text-muted-foreground">Awaiting run evidence</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">Driver ranking appears after an analysis is available.</p>
          </div>
        )}
      </div>

      <DriverBreakdown runs={runs} />

      {payload ? (
        <SectionCard title="Active Analysis Snapshot" description="Current execution summary" contentClassName="p-0">
          <div className="grid grid-cols-1 divide-y divide-border/60 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {[
              ["Industry", String(dataset.sector || context.sector || "-")],
              ["Decision", String(((payload.decision || {}) as Record<string, unknown>).recommended_action || "-")],
              ["Semantic Status", String(((payload.semantic_intelligence || {}) as Record<string, unknown>).status || "Ready")],
            ].map(([label, value]) => (
              <div key={label} className="px-4 py-3">
                <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
                <p className="mt-1 truncate text-sm font-semibold">{value}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}

      <SectionCard title="Recent Analyses" description="Open a run to inspect evidence and continue in the workspace">
        {history.error ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : null}
        {history.isLoading ? <LoadingState label="Loading analyses..." /> : null}
        {runs.length ? (
          <RecentRunsTable
            data={runs}
            onRestore={(run) =>
              context.setExecutionContext({ executionId: run.id, status: run.status, sector: run.sector })
            }
          />
        ) : (
          <RecentRunsEmptyState onLoadDemo={loadDemo} />
        )}
      </SectionCard>
    </PageShell>
  );
}
