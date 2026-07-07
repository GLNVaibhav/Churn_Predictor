"use client";

import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { PipelineFlow } from "@/components/pipeline/pipeline-flow";
import { MetricCard } from "@/components/shared/metric-card";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecution, useExecutionEvents, useExecutionPipeline } from "@/lib/hooks/use-execution";
import { canonicalPayload, canonicalStatus } from "@/lib/api/view-models";
import { mapCanonicalPipeline } from "@/lib/api/live-transform";
import { Clock, Layers, ShieldCheck, Workflow } from "lucide-react";

export default function PipelinePage() {
  const execution = useExecution();
  const payload = canonicalPayload(execution.data);
  const status = canonicalStatus(payload);
  const pipeline = useExecutionPipeline(undefined, status);
  useExecutionEvents(undefined, status);
  const stages = mapCanonicalPipeline(pipeline.data?.pipeline_state || (payload?.pipeline as Record<string, unknown> | undefined), status);
  const totalDuration = stages.reduce((sum, s) => sum + s.durationMs, 0);
  const completeCount = stages.filter((s) => s.status === "complete").length;

  return (
    <PageShell>
      {execution.error ? <ErrorBanner error={execution.error} onRetry={() => execution.refetch()} /> : null}
      {pipeline.error ? <ErrorBanner error={pipeline.error} onRetry={() => pipeline.refetch()} /> : null}
      {!payload && execution.isLoading ? <LoadingState label="Loading execution pipeline..." /> : null}
      {!payload && !execution.isLoading ? (
        <EmptyState title="No execution selected" description="Run analysis from the upload page or restore an execution from Dashboard." />
      ) : null}

      <div className="rounded-xl border border-primary/20 bg-gradient-to-br from-primary/10 via-transparent to-transparent p-5">
        <div className="flex items-center gap-2">
          <Workflow className="h-5 w-5 text-primary" />
          <h2 className="text-base font-semibold">Universal Churn Prediction Framework Execution Flow</h2>
        </div>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Each stage reflects the selected live execution. Polling continues while the execution is active and stops automatically once it reaches a terminal status.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard label="Pipeline Stages" value={`${stages.length}`} icon={Layers} description="Fixed execution order, non-configurable" />
        <MetricCard label="Stages Complete" value={`${completeCount} / ${stages.length}`} icon={ShieldCheck} description={`Selected run: ${status || "not started"}`} />
        <MetricCard label="Total Execution Time" value={`${totalDuration} ms`} icon={Clock} description="Backend-reported stage duration" />
      </div>

      <SectionCard
        title="Execution Flow"
        description="Upload Dataset -> Schema Intelligence -> Canonical Field Resolution -> Coverage Intelligence -> Concept Confidence -> Quality Gate -> Adaptive Routing -> Prediction -> Prediction Explanation -> Decision Intelligence"
      >
        <PipelineFlow stages={stages} />
      </SectionCard>
    </PageShell>
  );
}
