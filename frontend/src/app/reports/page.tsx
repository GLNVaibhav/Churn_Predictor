"use client";

import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { ReportExplorer } from "@/components/reports/report-explorer";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useAnalysisWorkspace } from "@/lib/hooks/use-analysis-workspace";
import { useExecutionContext } from "@/lib/context/execution-context";
import { reportCategories, reportContent, reportItems } from "@/lib/api/view-models";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function ReportsPage() {
  const ctx = useExecutionContext();
  const workspace = useAnalysisWorkspace();
  const payload = workspace.payload;

  return (
    <PageShell>
      {workspace.error ? <ErrorBanner error={workspace.error} onRetry={() => workspace.refetch()} /> : null}
      {!ctx.executionId ? (
        <EmptyState
          title="No execution selected"
          description="Open an analysis from history or start a new one."
          action={<Link href="/analyses"><Button size="sm">View Analyses</Button></Link>}
        />
      ) : workspace.isLoading ? (
        <LoadingState label="Loading reports..." />
      ) : null}
      {payload ? (
        <SectionCard title="Report Explorer" description="Executive, technical, and audit reports for the selected execution">
          <ReportExplorer
            categories={reportCategories}
            reports={reportItems(payload, workspace.reports)}
            getContent={(category) => reportContent(payload, category)}
          />
        </SectionCard>
      ) : null}
    </PageShell>
  );
}
