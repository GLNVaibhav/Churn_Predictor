"use client";

import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { SectionCard } from "@/components/shared/section-card";
import { RecentRunsTable } from "@/components/dashboard/recent-runs-table";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { useAnalysisWorkspace } from "@/lib/hooks/use-analysis-workspace";
import { useExecutionContext } from "@/lib/context/execution-context";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { sectorLabel } from "@/lib/constants/sectors";
import { frameworkKpis } from "@/lib/api/view-models";
import { PlusCircle, Activity, BookOpen, FileBarChart2, Microscope } from "lucide-react";

export default function DashboardPage() {
  const context = useExecutionContext();
  const workspace = useAnalysisWorkspace();
  const history = useExecutionHistory();
  const payload = workspace.payload;

  const framework = useQuery({
    queryKey: ["framework"],
    queryFn: ({ signal }) => apiRequest<{ framework_version: string; supported_sectors: string[] }>("/api/v1/framework", {}, signal),
  });

  const kpis = payload ? frameworkKpis(payload) : [];
  const runs = (history.data || []).slice(0, 8).map((run) => ({
    id: run.execution_id || "",
    sector: (run.sector || "telecom") as "telecom" | "banking" | "healthcare" | "ecommerce",
    mode: "Auto" as const,
    routingTier: "Green" as const,
    recordCount: 0,
    churnDetected: 0,
    submittedAt: run.created_at || run.started_at || "",
    status: run.status === "FAILED" ? "failed" as const : run.status === "RUNNING" ? "running" as const : "complete" as const,
  }));

  return (
    <PageShell>
      <div className="rounded-xl border border-blue-500/20 bg-gradient-to-br from-blue-500/10 via-transparent to-cyan-500/5 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-400">Mission Control</p>
            <h2 className="mt-1 text-xl font-semibold text-white">Universal Churn Intelligence Platform</h2>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              Enterprise decision intelligence — framework health, recent analyses, and one-click access to the analysis workspace.
            </p>
          </div>
          <Link href="/upload">
            <Button className="shrink-0"><PlusCircle className="mr-2 h-4 w-4" />New Analysis</Button>
          </Link>
        </div>
      </div>

      {workspace.error ? <ErrorBanner error={workspace.error} onRetry={() => workspace.refetch()} /> : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard label="Framework Health" value="Online" icon={Activity} description={`v${framework.data?.framework_version || "—"}`} />
        <MetricCard label="Industries" value={String(framework.data?.supported_sectors?.length || 0)} icon={BookOpen} description="Supported sectors" />
        <MetricCard label="Recent Runs" value={String(history.data?.length || 0)} icon={Microscope} description="Stored executions" />
        <MetricCard label="Reports" value={context.executionId ? "Available" : "—"} icon={FileBarChart2} description="Per execution" />
      </div>

      {payload && kpis.length ? (
        <SectionCard title="Active Execution Snapshot" description="Selected run — open workspace for full detail" contentClassName="p-0">
          <div className="grid grid-cols-2 divide-x divide-y divide-border/60 sm:grid-cols-3 xl:grid-cols-6 xl:divide-y-0">
            {kpis.slice(0, 6).map((kpi) => (
              <div key={kpi.id} className="px-4 py-3">
                <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{kpi.label}</p>
                <p className="text-base font-semibold tabular-nums">{kpi.value}</p>
              </div>
            ))}
          </div>
          <div className="border-t border-border/40 px-4 py-3">
            <Link href="/workspace">
              <Button variant="outline" size="sm">Open Analysis Workspace</Button>
            </Link>
          </div>
        </SectionCard>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Supported Industries" description="Framework-configured sectors">
          <div className="flex flex-wrap gap-2">
            {(framework.data?.supported_sectors || []).map((s) => (
              <span key={s} className="rounded-md border border-border/60 px-3 py-1.5 text-sm">{sectorLabel(s)}</span>
            ))}
          </div>
        </SectionCard>
        <SectionCard title="Quick Actions" description="Primary platform workflows">
          <div className="flex flex-col gap-2">
            <Link href="/upload"><Button variant="outline" className="w-full justify-start">New Analysis</Button></Link>
            <Link href="/analyses"><Button variant="outline" className="w-full justify-start">View History</Button></Link>
            <Link href="/monitoring"><Button variant="outline" className="w-full justify-start">Framework Monitoring</Button></Link>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Recent Analyses" description="Restore or open in workspace">
        {history.error ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : null}
        {history.isLoading ? <LoadingState label="Loading history..." /> : null}
        {runs.length ? (
          <RecentRunsTable
            data={runs}
            onRestore={(run) =>
              context.setExecutionContext({ executionId: run.id, status: run.status, sector: run.sector })
            }
          />
        ) : (
          <EmptyState title="No analyses yet" description="Start your first analysis to populate history." />
        )}
      </SectionCard>
    </PageShell>
  );
}
