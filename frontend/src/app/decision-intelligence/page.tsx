import { api } from "@/lib/api/client";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { ConceptConfidenceRadar } from "@/components/charts/concept-confidence-radar";
import { RoutingDecisionsTable } from "@/components/decision-intelligence/routing-decisions-table";

const sectorLabel: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  healthcare: "Healthcare",
  ecommerce: "E-commerce",
};

export default async function DecisionIntelligencePage() {
  const [routingDecisions, conceptConfidence] = await Promise.all([
    api.decisionIntelligence.getRoutingDecisions(),
    api.decisionIntelligence.getConceptConfidence(),
  ]);

  return (
    <PageShell>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <SectionCard
          title="Concept Confidence Breakdown"
          description="Business-concept reconstruction quality for the most recent telecom run"
          className="xl:col-span-1"
        >
          <ConceptConfidenceRadar data={conceptConfidence} />
        </SectionCard>

        <SectionCard title="Concept Sources" description="How each concept was reconstructed" className="xl:col-span-2" contentClassName="p-0">
          <div className="flex flex-col divide-y divide-border/60">
            {conceptConfidence.map((c) => (
              <div key={c.concept} className="flex items-center justify-between px-5 py-3.5">
                <div>
                  <p className="text-sm font-medium">{c.concept}</p>
                  <p className="text-xs text-muted-foreground">{c.source}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold tabular-nums">{c.confidence}%</p>
                  <p className="text-xs text-muted-foreground">
                    {c.reconstructable ? "Reconstructable" : "Not reconstructable"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title="Routing Decisions"
        description="Adaptive Routing output — the single source of truth for model selection across every run"
      >
        <RoutingDecisionsTable data={routingDecisions} />
      </SectionCard>
    </PageShell>
  );
}
