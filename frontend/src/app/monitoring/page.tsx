"use client";

import { PageShell } from "@/components/layout/page-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { SectionCard } from "@/components/shared/section-card";
import { ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { Activity, Clock, Gauge, Layers } from "lucide-react";

type FrameworkInfo = {
  framework_version: string;
  runtime_version: string;
  supported_sectors: string[];
  available_modules: string[];
  coverage_version?: string;
  prediction_intelligence_version?: string;
};

export default function MonitoringPage() {
  const history = useExecutionHistory();
  const framework = useQuery({
    queryKey: ["framework"],
    queryFn: ({ signal }) => apiRequest<FrameworkInfo>("/api/v1/framework", {}, signal),
  });

  const runs = history.data || [];
  const succeeded = runs.filter((r) => r.status === "SUCCEEDED").length;
  const failed = runs.filter((r) => r.status === "FAILED").length;
  const avgRuntime =
    runs.reduce((sum, r) => sum + Number(r.execution_time_ms || 0), 0) / (runs.length || 1);

  return (
    <PageShell>
      {history.error ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : null}
      {framework.error ? <ErrorBanner error={framework.error as Error} onRetry={() => framework.refetch()} /> : null}
      {(history.isLoading || framework.isLoading) ? <LoadingState label="Loading monitoring data..." /> : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard label="Framework Health" value="Online" icon={Activity} description="Backend API reachable" />
        <MetricCard label="Recent Executions" value={String(runs.length)} icon={Layers} description={`${succeeded} succeeded · ${failed} failed`} />
        <MetricCard label="Avg Runtime" value={`${Math.round(avgRuntime)} ms`} icon={Clock} description="Across stored executions" />
        <MetricCard label="Pipeline Version" value={framework.data?.framework_version || "—"} icon={Gauge} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Framework Versions" description="Live version stamps from universal_churn">
          {framework.data ? (
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-muted-foreground">Framework</dt><dd className="font-medium">{framework.data.framework_version}</dd></div>
              <div><dt className="text-muted-foreground">Runtime</dt><dd className="font-medium">{framework.data.runtime_version}</dd></div>
              <div><dt className="text-muted-foreground">Coverage</dt><dd className="font-medium">{framework.data.coverage_version || "—"}</dd></div>
              <div><dt className="text-muted-foreground">Intelligence</dt><dd className="font-medium">{framework.data.prediction_intelligence_version || "—"}</dd></div>
            </dl>
          ) : null}
        </SectionCard>
        <SectionCard title="Supported Industries" description="Sectors configured in the framework">
          <div className="flex flex-wrap gap-2">
            {(framework.data?.supported_sectors || []).map((s) => (
              <span key={s} className="rounded-md border border-border/60 bg-muted/30 px-2.5 py-1 text-xs capitalize">{s}</span>
            ))}
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Framework Components" description="Available intelligence modules">
        <div className="flex flex-wrap gap-2">
          {(framework.data?.available_modules || []).map((m) => (
            <span key={m} className="rounded-md bg-blue-500/10 px-2.5 py-1 text-xs text-blue-300">{m}</span>
          ))}
        </div>
      </SectionCard>
    </PageShell>
  );
}
