"use client";

import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { LoadingState, ErrorBanner } from "@/components/shared/query-states";

export default function SettingsPage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => apiRequest<{ status: string; framework_version?: string }>("/api/v1/health", {}, signal),
  });
  const framework = useQuery({
    queryKey: ["framework"],
    queryFn: ({ signal }) => apiRequest<{ framework_version: string; runtime_version: string; contract_version: string }>("/api/v1/framework", {}, signal),
  });

  return (
    <PageShell>
      <SectionCard title="API Configuration" description="Frontend environment and backend connectivity">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="api-endpoint">Backend API Endpoint</Label>
            <Input id="api-endpoint" defaultValue={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"} disabled />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>API Status</Label>
            {health.isLoading ? <LoadingState label="Checking..." /> : null}
            {health.error ? <ErrorBanner error={health.error as Error} /> : null}
            {health.data ? (
              <Badge variant="outline" className="w-fit border-emerald-500/30 text-emerald-400">{health.data.status}</Badge>
            ) : null}
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Framework Information" description="Version stamps from live backend">
        {framework.isLoading ? <LoadingState /> : null}
        {framework.data ? (
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div><dt className="text-muted-foreground">Framework</dt><dd>{framework.data.framework_version}</dd></div>
            <div><dt className="text-muted-foreground">Runtime</dt><dd>{framework.data.runtime_version}</dd></div>
            <div><dt className="text-muted-foreground">Contract</dt><dd>{framework.data.contract_version}</dd></div>
            <div><dt className="text-muted-foreground">Default Mode</dt><dd>auto</dd></div>
          </dl>
        ) : null}
      </SectionCard>

      <SectionCard title="Environment" description="Deployment context">
        <p className="text-sm text-muted-foreground">Node env: {process.env.NODE_ENV}</p>
        <Separator className="my-4" />
        <p className="text-xs text-muted-foreground">Set NEXT_PUBLIC_API_URL to point at a different FastAPI instance.</p>
      </SectionCard>

      <SectionCard title="About UCIF" description="Universal Churn Intelligence Framework">
        <p className="text-sm text-muted-foreground">
          UCIF is an enterprise AI Decision Intelligence platform. Business intelligence is owned exclusively by
          <code className="mx-1 text-xs"> universal_churn</code> — the backend orchestrates; the frontend renders.
        </p>
      </SectionCard>
    </PageShell>
  );
}
