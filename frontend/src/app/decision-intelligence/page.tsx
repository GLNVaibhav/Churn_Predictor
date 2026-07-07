"use client";

import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { ConceptConfidenceRadar } from "@/components/charts/concept-confidence-radar";
import { RoutingDecisionsTable } from "@/components/decision-intelligence/routing-decisions-table";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecution, useExecutionContextQuery, useExecutionDecision, useExecutionReports } from "@/lib/hooks/use-execution";
import { useDevMode } from "@/lib/context/dev-mode-context";
import { canonicalPayload, conceptConfidence, routingDecisions } from "@/lib/api/view-models";

function DeveloperPanel({ payload }: { payload: Record<string, unknown> }) {
  const sections = [
    ["Execution", payload.execution],
    ["Contracts", { coverage: payload.coverage, quality: payload.quality, prediction: payload.prediction }],
    ["Routing", payload.routing],
    ["Metadata", payload.metadata],
    ["Timing", payload.execution],
    ["Reports", payload.reports],
    ["Raw Context", payload],
  ];

  return (
    <SectionCard title="Developer Mode" description="Execution context grouped by backend contract section">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {sections.map(([title, value]) => (
          <div key={String(title)} className="rounded-lg border border-border/60 bg-muted/20 p-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">{String(title)}</p>
            <pre className="max-h-72 overflow-auto text-xs text-muted-foreground">{JSON.stringify(value || {}, null, 2)}</pre>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

export default function DecisionIntelligencePage() {
  const execution = useExecution();
  const decision = useExecutionDecision();
  const contextQuery = useExecutionContextQuery();
  const reports = useExecutionReports();
  const { developerMode } = useDevMode();
  const payload = canonicalPayload(execution.data);
  const routing = routingDecisions(payload);
  const concepts = conceptConfidence(payload);

  return (
    <PageShell>
      {decision.error ? <ErrorBanner error={decision.error} onRetry={() => decision.refetch()} /> : null}
      {execution.isLoading || decision.isLoading || contextQuery.isLoading || reports.isLoading ? <LoadingState label="Loading decision intelligence..." /> : null}
      {!payload && !execution.isLoading ? (
        <EmptyState title="No decision context" description="Run analysis or restore an execution with Decision Intelligence output." />
      ) : null}

      {payload ? (
        <>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <SectionCard title="Concept Confidence Breakdown" description="Business-concept reconstruction quality for the selected run" className="xl:col-span-1">
              {concepts.length ? <ConceptConfidenceRadar data={concepts} /> : <EmptyState title="No concept confidence" description="The backend did not return concept-level confidence for this execution." />}
            </SectionCard>

            <SectionCard title="Concept Sources" description="How each concept was reconstructed" className="xl:col-span-2" contentClassName="p-0">
              <div className="flex flex-col divide-y divide-border/60">
                {concepts.map((c) => (
                  <div key={c.concept} className="flex items-center justify-between px-5 py-3.5">
                    <div>
                      <p className="text-sm font-medium">{c.concept}</p>
                      <p className="text-xs text-muted-foreground">{c.source}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold tabular-nums">{c.confidence}%</p>
                      <p className="text-xs text-muted-foreground">{c.reconstructable ? "Reconstructable" : "Not reconstructable"}</p>
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>

          <SectionCard title="Routing Decisions" description="Adaptive Routing output from the backend">
            {routing.length ? <RoutingDecisionsTable data={routing} /> : <EmptyState title="No routing decision" description="The selected execution has no routing output." />}
          </SectionCard>

          {developerMode ? <DeveloperPanel payload={{ ...payload, context: contextQuery.data?.context, decision: decision.data?.decision, reports: reports.data?.reports }} /> : null}
        </>
      ) : null}
    </PageShell>
  );
}
