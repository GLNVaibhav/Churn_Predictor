"use client";

import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { sectorLabel } from "@/lib/constants/sectors";

type FrameworkInfo = {
  framework_version: string;
  supported_sectors: string[];
  available_modules: string[];
};

const KNOWLEDGE_DOCS = [
  { title: "Coverage Intelligence", body: "Measures feature availability and semantic recovery. Owned by universal_churn/coverage.py." },
  { title: "Quality Gate", body: "Validates leakage, duplicates, and column quality before prediction. Owned by universal_churn/quality_gate.py." },
  { title: "Adaptive Routing", body: "Selects sector, universal, or refusal based on coverage and quality. Owned by universal_churn/routing.py." },
  { title: "Decision Intelligence", body: "Synthesizes business and technical confidence into recommended actions." },
  { title: "Business Reasoning", body: "Generates narrative explanations for prediction outcomes." },
];

export default function KnowledgePage() {
  const framework = useQuery({
    queryKey: ["framework"],
    queryFn: ({ signal }) => apiRequest<FrameworkInfo>("/api/v1/framework", {}, signal),
  });

  return (
    <PageShell>
      {framework.error ? <ErrorBanner error={framework.error as Error} onRetry={() => framework.refetch()} /> : null}
      {framework.isLoading ? <LoadingState label="Loading knowledge base..." /> : null}

      <SectionCard title="Knowledge Base" description="Framework-owned business intelligence modules (read-only reference)">
        <p className="text-sm text-muted-foreground">
          Business rules and sector configuration live in <code className="text-xs">universal_churn/knowledge_base.py</code> and sector YAML.
          The backend exposes module metadata only — no business logic is duplicated in the platform layer.
        </p>
      </SectionCard>

      <SectionCard title="Supported Sectors" description="Industries with trained sector models">
        <div className="grid gap-3 sm:grid-cols-2">
          {(framework.data?.supported_sectors || []).map((sector) => (
            <div key={sector} className="rounded-lg border border-border/60 bg-muted/20 p-4">
              <p className="font-medium">{sectorLabel(sector)}</p>
              <p className="mt-1 text-xs text-muted-foreground">Sector pipeline · schema resolution · concept confidence</p>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Pipeline Documentation" description="Core framework components">
        <div className="space-y-4">
          {KNOWLEDGE_DOCS.map((doc) => (
            <div key={doc.title} className="border-b border-border/40 pb-4 last:border-0">
              <p className="font-medium">{doc.title}</p>
              <p className="mt-1 text-sm text-muted-foreground">{doc.body}</p>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Framework Components" description={`Pipeline v${framework.data?.framework_version || "—"}`}>
        <ul className="grid gap-2 sm:grid-cols-2 text-sm">
          {(framework.data?.available_modules || []).map((m) => (
            <li key={m} className="rounded-md border border-border/40 px-3 py-2 font-mono text-xs">{m}</li>
          ))}
        </ul>
      </SectionCard>
    </PageShell>
  );
}
