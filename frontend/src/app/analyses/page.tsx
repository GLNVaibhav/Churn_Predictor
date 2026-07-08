"use client";

import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { RecentRunsTable } from "@/components/dashboard/recent-runs-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { useExecutionContext } from "@/lib/context/execution-context";
import { sectorLabel } from "@/lib/constants/sectors";
import { PlusCircle, ExternalLink } from "lucide-react";

export default function AnalysesPage() {
  const history = useExecutionHistory();
  const ctx = useExecutionContext();

  const runs = (history.data || []).map((run) => ({
    id: run.execution_id || "",
    sector: (run.sector || "telecom") as "telecom" | "banking" | "healthcare" | "ecommerce",
    mode: "Auto" as const,
    routingTier: "Green" as const,
    recordCount: 0,
    churnDetected: 0,
    submittedAt: run.created_at || run.started_at || "",
    status: run.status === "FAILED" ? "failed" as const : run.status === "RUNNING" ? "running" as const : "complete" as const,
  }));

  return (
    <PageShell>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Analysis History</h2>
          <p className="text-sm text-muted-foreground">All executions persisted by the platform</p>
        </div>
        <Link href="/upload">
          <Button size="sm"><PlusCircle className="mr-2 h-4 w-4" />New Analysis</Button>
        </Link>
      </div>

      {history.error ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : null}
      {history.isLoading ? <LoadingState label="Loading execution history..." /> : null}

      <SectionCard title="Executions" description="Open any analysis in the unified workspace" contentClassName="p-0">
        {runs.length ? (
          <div className="divide-y divide-border/60">
            {runs.map((run) => (
              <div key={run.id} className="flex items-center justify-between gap-4 px-5 py-4">
                <div>
                  <p className="font-mono text-xs text-muted-foreground">{run.id.slice(0, 12)}…</p>
                  <p className="text-sm font-medium">{sectorLabel(run.sector)} · {run.mode}</p>
                  <p className="text-xs text-muted-foreground">{new Date(run.submittedAt).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{run.status}</Badge>
                  <Link href="/workspace">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        ctx.setExecutionContext({ executionId: run.id, status: run.status, sector: run.sector });
                      }}
                    >
                      <ExternalLink className="mr-1 h-3.5 w-3.5" />Open
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No analyses yet" description="Completed runs appear here after you start an analysis." />
        )}
      </SectionCard>

      {runs.length > 0 ? (
        <SectionCard title="Quick Restore" description="Restore execution context across the platform">
          <RecentRunsTable
            data={runs}
            onRestore={(run) =>
              ctx.setExecutionContext({ executionId: run.id, status: run.status, sector: run.sector })
            }
          />
        </SectionCard>
      ) : null}
    </PageShell>
  );
}
