"use client";

import { PageShell } from "@/components/layout/page-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { SectionCard } from "@/components/shared/section-card";
import { ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { executionMetrics, serviceHealthState } from "@/lib/monitoring-metrics";
import { sectorLabel } from "@/lib/constants/sectors";
import { Activity, Clock, Gauge, Layers, ShieldCheck } from "lucide-react";

type ServiceInfo = {
  supported_sectors: string[];
};

type HealthInfo = {
  status: string;
};

export default function MonitoringPage() {
  const history = useExecutionHistory();
  const service = useQuery({
    queryKey: ["framework"],
    queryFn: ({ signal }) => apiRequest<ServiceInfo>("/api/v1/framework", {}, signal),
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => apiRequest<HealthInfo>("/api/v1/health", {}, signal),
    refetchInterval: 30_000,
  });

  const runs = history.data || [];
  const metrics = executionMetrics(runs);
  const healthState = serviceHealthState(health.data?.status, health.isPending, health.isError);
  const healthStyles = {
    HEALTHY: "border-emerald-500/25 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-200",
    DEGRADED: "border-amber-500/25 bg-amber-50 text-amber-800 dark:bg-amber-950/30 dark:text-amber-200",
    UNAVAILABLE: "border-destructive/25 bg-destructive/10 text-destructive",
    UNKNOWN: "border-border bg-muted text-muted-foreground",
  }[healthState];

  return (
    <PageShell>
      {history.error ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : null}
      {service.error ? <ErrorBanner error={service.error as Error} onRetry={() => service.refetch()} /> : null}
      {health.error ? <ErrorBanner error={health.error as Error} onRetry={() => health.refetch()} /> : null}
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
          <div role="status" className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold ${healthStyles}`}>
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            {healthState.charAt(0) + healthState.slice(1).toLowerCase()}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard label="Backend Health" value={healthState.charAt(0) + healthState.slice(1).toLowerCase()} icon={Activity} description={health.data?.status ? `API status: ${health.data.status}` : "Health endpoint has not reported a status"} />
        <MetricCard label="Recent Analyses" value={String(metrics.total)} icon={Layers} description={`${metrics.succeeded} completed, ${metrics.failed} failed`} />
        <MetricCard label="Avg Runtime" value={metrics.averageRuntimeMs === null ? "—" : `${Math.round(metrics.averageRuntimeMs)} ms`} icon={Clock} description={metrics.total ? "Across saved runs" : "No execution timings available"} />
        <MetricCard label="Success Rate" value={metrics.successRatePercent === null ? "—" : `${metrics.successRatePercent}%`} icon={Gauge} description={metrics.total ? "Current workspace executions" : "No executions to calculate a rate"} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Analysis Reliability" description="Recent execution health for this workspace">
          <div className="space-y-3">
            {[
              ["Completed analyses", metrics.succeeded],
              ["Failed analyses", metrics.failed],
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
