"use client";

import { PageShell } from "@/components/layout/page-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { SectionCard } from "@/components/shared/section-card";
import { StatusCard } from "@/components/shared/status-card";
import { RecentRunsTable } from "@/components/dashboard/recent-runs-table";
import { StageStatusBadge } from "@/components/shared/status-badge";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecution, useExecutionHistory, useExecutionPredictions } from "@/lib/hooks/use-execution";
import { useExecutionContext } from "@/lib/context/execution-context";
import {
  canonicalPayload,
  dashboardStats,
  frameworkKpis,
  predictionRows,
  recentRun,
  sectorHealth,
} from "@/lib/api/view-models";
import { Gauge, Percent, ShieldCheck, Sparkles } from "lucide-react";

const iconMap = {
  "total-predictions": Sparkles,
  "avg-churn-rate": Percent,
  "concept-confidence": Gauge,
  "routing-green": ShieldCheck,
};

export default function DashboardPage() {
  const context = useExecutionContext();
  const execution = useExecution();
  const predictionsQuery = useExecutionPredictions();
  const history = useExecutionHistory();
  const payload = canonicalPayload(execution.data);
  const rows = predictionRows(payload, predictionsQuery.data?.predictions || []);
  const stats = dashboardStats(payload, rows);
  const kpis = frameworkKpis(payload);
  const health = sectorHealth(payload, rows);
  const runs = [
    ...recentRun(payload),
    ...(history.data || []).map((run) => ({
      id: run.execution_id,
      sector: "telecom" as const,
      mode: "Auto" as const,
      routingTier: "Green" as const,
      recordCount: 0,
      churnDetected: 0,
      submittedAt: run.created_at || run.started_at || "",
      status: run.status === "FAILED" ? "failed" as const : run.status === "RUNNING" ? "running" as const : "complete" as const,
    })),
  ].filter((run, idx, all) => all.findIndex((r) => r.id === run.id) === idx);

  if (!context.executionId && history.isLoading) {
    return <PageShell><LoadingState /></PageShell>;
  }

  return (
    <PageShell>
      {execution.error ? <ErrorBanner error={execution.error} onRetry={() => execution.refetch()} /> : null}
      {!context.executionId ? (
        <EmptyState title="No execution selected" description="Upload a CSV and run analysis, or restore a previous execution from history." />
      ) : execution.isLoading ? (
        <LoadingState label="Loading execution..." />
      ) : null}

      {payload ? (
        <>
          <SectionCard
            title="Framework Intelligence Snapshot"
            description="Live indicators synthesized from the selected execution across Coverage, Concept Confidence, Quality Gate, and Adaptive Routing"
            contentClassName="p-0"
          >
            <div className="grid grid-cols-2 divide-x divide-y divide-border/60 sm:grid-cols-3 xl:grid-cols-9 xl:divide-y-0">
              {kpis.map((kpi) => (
                <div key={kpi.id} className="flex flex-col gap-1 px-4 py-4">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{kpi.label}</p>
                  <p className="text-lg font-semibold tabular-nums leading-tight">{kpi.value}</p>
                  {kpi.description ? <span className="text-[11px] text-muted-foreground">{kpi.description}</span> : null}
                </div>
              ))}
            </div>
          </SectionCard>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {stats.map((stat) => (
              <MetricCard
                key={stat.id}
                label={stat.label}
                value={stat.value}
                delta={stat.delta}
                deltaDirection={stat.deltaDirection}
                description={stat.description}
                icon={iconMap[stat.id as keyof typeof iconMap]}
              />
            ))}
          </div>

          <SectionCard title="Sector Health" description="Selected execution status by detected sector" contentClassName="p-0">
            <div className="flex flex-col divide-y divide-border/60">
              {health.map((sector) => (
                <div key={sector.sector} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-sm font-medium">{sector.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {sector.totalRecords.toLocaleString()} records, {sector.avgConceptConfidence}% confidence
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold tabular-nums">{sector.churnRate}%</p>
                    <StageStatusBadge status={sector.status} className="mt-1" />
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
            {health.map((sector) => (
              <StatusCard
                key={sector.sector}
                title={sector.label}
                subtitle={`Last run ${new Date(sector.lastRunAt).toLocaleString()}`}
                status={sector.status}
                metrics={[
                  { label: "Churn Rate", value: `${sector.churnRate}%` },
                  { label: "Concept Confidence", value: `${sector.avgConceptConfidence}%` },
                ]}
              />
            ))}
          </div>
        </>
      ) : null}

      <SectionCard title="Recent Prediction Runs" description="Select a previous execution to restore it across the app">
        {history.error ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : null}
        {runs.length ? (
          <RecentRunsTable
            data={runs}
            onRestore={(run) =>
              context.setExecutionContext({
                executionId: run.id,
                status: run.status,
                sector: run.sector,
              })
            }
          />
        ) : (
          <EmptyState title="No execution history" description="Completed runs will appear here after analysis starts." />
        )}
      </SectionCard>
    </PageShell>
  );
}
