"use client";

import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { ReportExplorer } from "@/components/reports/report-explorer";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useExecution, useExecutionReports } from "@/lib/hooks/use-execution";
import { canonicalPayload, reportCategories, reportContent, reportItems } from "@/lib/api/view-models";

export default function ReportsPage() {
  const execution = useExecution();
  const reportsQuery = useExecutionReports();
  const payload = canonicalPayload(execution.data);
  const reports = reportItems(payload, reportsQuery.data?.reports || []);

  return (
    <PageShell>
      {reportsQuery.error ? <ErrorBanner error={reportsQuery.error} onRetry={() => reportsQuery.refetch()} /> : null}
      {execution.isLoading || reportsQuery.isLoading ? <LoadingState label="Loading reports..." /> : null}
      {!payload && !execution.isLoading ? (
        <EmptyState title="No execution selected" description="Run analysis or restore an execution to browse backend reports." />
      ) : null}
      {payload ? (
        <SectionCard title="Report Explorer" description="Browse reports generated for the selected execution">
          <ReportExplorer categories={reportCategories} reports={reports} getContent={(category) => reportContent(payload, category)} />
        </SectionCard>
      ) : null}
    </PageShell>
  );
}
