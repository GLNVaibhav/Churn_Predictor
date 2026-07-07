import { api } from "@/lib/api/client";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { PipelineFlow } from "@/components/pipeline/pipeline-flow";
import { MetricCard } from "@/components/shared/metric-card";
import { Clock, Layers, ShieldCheck, Workflow } from "lucide-react";

export default async function PipelinePage() {
  const stages = await api.pipeline.getStages();
  const totalDuration = stages.reduce((sum, s) => sum + s.durationMs, 0);
  const completeCount = stages.filter((s) => s.status === "complete").length;

  return (
    <PageShell>
      <div className="rounded-xl border border-primary/20 bg-gradient-to-br from-primary/10 via-transparent to-transparent p-5">
        <div className="flex items-center gap-2">
          <Workflow className="h-5 w-5 text-primary" />
          <h2 className="text-base font-semibold">Universal Churn Prediction Framework — Execution Flow</h2>
        </div>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          This is the exact execution flow implemented by the CLI: every input dataset moves through
          schema resolution, coverage and concept scoring, a quality gate, and adaptive routing before a
          model produces a prediction and an auditable decision record. Click any stage below to inspect
          its mock output for the most recent run.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard label="Pipeline Stages" value={`${stages.length}`} icon={Layers} description="Fixed execution order, non-configurable" />
        <MetricCard label="Stages Complete" value={`${completeCount} / ${stages.length}`} icon={ShieldCheck} description="Most recent run: TEL-run-1042" />
        <MetricCard label="Total Execution Time" value={`${totalDuration} ms`} icon={Clock} description="Sum of all stage durations" />
      </div>

      <SectionCard
        title="Execution Flow"
        description="Upload Dataset → Schema Intelligence → Canonical Field Resolution → Coverage Intelligence → Concept Confidence → Quality Gate → Adaptive Routing → Prediction → Prediction Explanation → Decision Intelligence"
      >
        <PipelineFlow stages={stages} />
      </SectionCard>
    </PageShell>
  );
}
