import { api } from "@/lib/api/client";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { ReportExplorer } from "@/components/reports/report-explorer";

export default async function ReportsPage() {
  const [reports, categories] = await Promise.all([
    api.reports.getAll(),
    api.reports.getCategories(),
  ]);

  return (
    <PageShell>
      <SectionCard
        title="Report Explorer"
        description="Browse by category to see a synthesized report, or scan generated report files below"
      >
        <ReportExplorer categories={categories} reports={reports} />
      </SectionCard>
    </PageShell>
  );
}
