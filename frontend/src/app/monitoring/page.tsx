"use client";

import { PageShell } from "@/components/layout/page-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { SectionCard } from "@/components/shared/section-card";
import { ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { sectorLabel } from "@/lib/constants/sectors";
import { Activity, Clock, Gauge, Layers, ShieldCheck } from "lucide-react";

type ServiceInfo = {
  supported_sectors: string[];
};

export default function MonitoringPage() {
  const history = useExecutionHistory();
  const service = useQuery({
    queryKey: ["framework"],
    queryFn: ({ signal }) => apiRequest<ServiceInfo>("/api/v1/framework", {}, signal),
  });

  const runs = history.data || [];
  const succeeded = runs.filter((run) => run.status === "SUCCEEDED").length;
  const failed = runs.filter((run) => run.status === "FAILED").length;
  const avgRuntime = runs.reduce((sum, run) => sum + Number(run.execution_time_ms || 0), 0) / (runs.length || 1);
  const successRate = runs.length ? Math.round((succeeded / runs.length) * 100) : 100;

  return (
    <PageShell>
      {history.error ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : null}
      {service.error ? <ErrorBanner error={service.error as Error} onRetry={() => service.refetch()} /> : null}
      {history.isLoading || service.isLoading ? <LoadingState label="Loading activity data..." /> : null}

      <div className="premium-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">Workspace health</p>
            <h2 className="mt-2 max-w-3xl text-2xl font-semibold tracking-tight">
              Track analysis reliability and customer-risk activity.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Monitor service availability, recent run volume, completion rate, and supported industries without exposing implementation details.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-emerald-500/25 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-200">
            <ShieldCheck className="h-4 w-4" />
            Operational
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard label="Service" value="Online" icon={Activity} description="Analysis engine reachable" />
        <MetricCard label="Recent Analyses" value={String(runs.length)} icon={Layers} description={`${succeeded} completed, ${failed} failed`} />
        <MetricCard label="Avg Runtime" value={`${Math.round(avgRuntime)} ms`} icon={Clock} description="Across saved runs" />
        <MetricCard label="Success Rate" value={`${successRate}%`} icon={Gauge} description="Current workspace" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Analysis Reliability" description="Recent execution health for this workspace">
          <div className="space-y-3">
            {[
              ["Completed analyses", succeeded],
              ["Failed analyses", failed],
              ["Saved analyses", runs.length],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between rounded-md border border-border bg-background/75 px-3 py-2 text-sm">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-semibold tabular-nums">{value}</span>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Available Industries" description="Customer sectors available for analysis">
          <div className="flex flex-wrap gap-2">
            {(service.data?.supported_sectors || []).map((sector) => (
              <span key={sector} className="rounded-md border border-border/60 bg-background/75 px-2.5 py-1 text-xs">
                {sectorLabel(sector)}
              </span>
            ))}
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}
