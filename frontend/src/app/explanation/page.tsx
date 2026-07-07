"use client";

import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { FeatureContributionChart } from "@/components/charts/feature-contribution-chart";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecution, useExecutionPredictions } from "@/lib/hooks/use-execution";
import { canonicalPayload, explanations } from "@/lib/api/view-models";

const sectorLabel: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  healthcare: "Healthcare",
  ecommerce: "E-commerce",
};

export default function ExplanationPage() {
  const execution = useExecution();
  const predictionQuery = useExecutionPredictions();
  const payload = canonicalPayload(execution.data);
  const items = explanations(payload, predictionQuery.data?.predictions || []);

  return (
    <PageShell>
      {predictionQuery.error ? <ErrorBanner error={predictionQuery.error} onRetry={() => predictionQuery.refetch()} /> : null}
      {execution.isLoading || predictionQuery.isLoading ? <LoadingState label="Loading explanations..." /> : null}
      {!items.length && !predictionQuery.isLoading ? (
        <EmptyState title="No explanations available" description="The selected execution has no prediction explanation output yet." />
      ) : null}

      {items.length ? (
        <>
          <SectionCard title="Prediction Explanation Layer" description="Live explanation summaries returned by the backend.">
            <p className="text-sm text-muted-foreground">Showing {items.length} explained records from the selected execution.</p>
          </SectionCard>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {items.map((exp) => (
              <SectionCard
                key={exp.recordId}
                title={exp.customerId}
                description={`${sectorLabel[exp.sector]} - Churn probability ${(exp.churnProbability * 100).toFixed(1)}%`}
                action={<Badge variant="outline">{sectorLabel[exp.sector]}</Badge>}
              >
                <p className="text-sm leading-relaxed text-muted-foreground">{exp.narrative}</p>
                <div className="mt-5">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Top Feature Contributions</p>
                  <FeatureContributionChart data={exp.topContributions} />
                </div>
                <div className="mt-4">
                  <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Concept Confidence</p>
                  <div className="flex flex-col gap-2.5">
                    {exp.concepts.map((c) => (
                      <div key={c.name}>
                        <div className="mb-1 flex items-center justify-between text-xs">
                          <span className="font-medium">{c.name}</span>
                          <span className="tabular-nums text-muted-foreground">{c.confidence}%</span>
                        </div>
                        <Progress value={c.confidence} className="h-1.5" />
                      </div>
                    ))}
                  </div>
                </div>
              </SectionCard>
            ))}
          </div>
        </>
      ) : null}
    </PageShell>
  );
}
