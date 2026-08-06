"use client";

import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import {
  RecentRunsEmptyState,
  RecentRunsTable,
  demoRunForSector,
  type DashboardRun,
} from "@/components/dashboard/recent-runs-table";
import { Button } from "@/components/ui/button";
import { ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { useExecutionContext } from "@/lib/context/execution-context";
import type { Sector } from "@/lib/types";
import { PlusCircle } from "lucide-react";

export default function AnalysesPage() {
  const history = useExecutionHistory();
  const ctx = useExecutionContext();

  const runs: DashboardRun[] = (history.data || []).map((run) => ({
    id: run.execution_id || "",
    sector: (run.sector || "telecom") as Sector,
    mode: "Sector",
    routingTier: "Green",
    recordCount: 0,
    churnDetected: 0,
    avgRisk: 0,
    atRiskRate: 0,
    topDriver: "Open workspace for driver evidence",
    semanticStatus: "Ready",
    submittedAt: run.created_at || run.started_at || "",
    status: run.status === "FAILED" ? "failed" : run.status === "RUNNING" ? "running" : "complete",
  }));

  function restoreRun(run: DashboardRun) {
    ctx.setExecutionContext({ executionId: run.id, status: run.status, sector: run.sector });
  }

  function loadDemo(sector: Sector) {
    restoreRun(demoRunForSector(sector));
  }

  return (
    <PageShell>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Analysis History</h2>
          <p className="text-sm text-muted-foreground">Previous churn runs, restored into the same workspace model.</p>
        </div>
        <Link href="/upload">
          <Button size="sm">
            <PlusCircle className="mr-2 h-4 w-4" />
            New Run
          </Button>
        </Link>
      </div>

      {history.error ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : null}
      {history.isLoading ? <LoadingState label="Loading execution history..." /> : null}

      <SectionCard
        title="Recent Analyses"
        description="Open any run to inspect predictions, evidence, comparison, and decision support"
        contentClassName="p-0"
      >
        <div className="p-5">
          {runs.length ? (
            <RecentRunsTable data={runs} onRestore={restoreRun} />
          ) : (
            <RecentRunsEmptyState onLoadDemo={loadDemo} />
          )}
        </div>
      </SectionCard>
    </PageShell>
  );
}
