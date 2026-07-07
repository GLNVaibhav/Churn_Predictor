"use client";

import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { MetricCard } from "@/components/shared/metric-card";
import { PredictionsTable } from "@/components/predictions/predictions-table";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecution, useExecutionPredictions } from "@/lib/hooks/use-execution";
import { canonicalPayload, predictions } from "@/lib/api/view-models";
import { AlertTriangle, Percent, Sparkles, Users } from "lucide-react";

export default function PredictionsPage() {
  const execution = useExecution();
  const predictionQuery = useExecutionPredictions();
  const payload = canonicalPayload(execution.data);
  const records = predictions(payload, predictionQuery.data?.predictions || []);
  const avgProbability = records.length ? records.reduce((sum, p) => sum + p.churnProbability, 0) / records.length : 0;
  const critical = records.filter((p) => p.riskTier === "Critical").length;
  const refused = records.filter((p) => p.routingTier === "Red").length;

  return (
    <PageShell>
      {predictionQuery.error ? <ErrorBanner error={predictionQuery.error} onRetry={() => predictionQuery.refetch()} /> : null}
      {execution.isLoading || predictionQuery.isLoading ? <LoadingState label="Loading predictions..." /> : null}
      {!records.length && !predictionQuery.isLoading ? (
        <EmptyState title="No predictions available" description="Run analysis or restore an execution with prediction output." />
      ) : null}

      {records.length ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Total Records" value={`${records.length}`} icon={Users} description="From selected execution" />
            <MetricCard label="Avg. Churn Probability" value={`${(avgProbability * 100).toFixed(1)}%`} icon={Percent} />
            <MetricCard label="Critical Risk" value={`${critical}`} icon={AlertTriangle} description="Requires immediate attention" />
            <MetricCard label="Refused Predictions" value={`${refused}`} icon={Sparkles} description="Red routing tier" />
          </div>

          <SectionCard title="Scored Records" description="Predictions returned by the backend for the selected execution">
            <PredictionsTable data={records} />
          </SectionCard>
        </>
      ) : null}
    </PageShell>
  );
}
