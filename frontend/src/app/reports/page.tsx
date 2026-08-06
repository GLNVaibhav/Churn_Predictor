"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { ReportExplorer } from "@/components/reports/report-explorer";
import { ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { useAnalysisWorkspace } from "@/lib/hooks/use-analysis-workspace";
import { useExecutionContext } from "@/lib/context/execution-context";
import { reportCategories, reportContent, reportItems } from "@/lib/api/view-models";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Sector } from "@/lib/types";
import { demoRunForSector } from "@/components/dashboard/recent-runs-table";
import { Activity, BrainCircuit, FileBarChart2, FileSpreadsheet, ShieldCheck } from "lucide-react";

const sectors: Sector[] = ["telecom", "banking", "ecommerce", "healthcare"];
const sectorLabel: Record<Sector, string> = {
  telecom: "Telecom",
  banking: "Banking",
  ecommerce: "E-commerce",
  healthcare: "Healthcare",
};

const reportPreview = [
  { title: "Executive", description: "Board-ready churn risk summary and recommended retention actions.", icon: FileBarChart2 },
  { title: "Diagnostic", description: "Coverage, schema quality, routing confidence, and readiness gaps.", icon: Activity },
  { title: "Prediction", description: "Cohorts, risk tiers, and customer-level prediction evidence.", icon: BrainCircuit },
  { title: "Decision", description: "Action plan shaped by ABIL context, risk severity, and business impact.", icon: ShieldCheck },
];

function ReportsPreview({ activeSector }: { activeSector: Sector }) {
  const run = demoRunForSector(activeSector);
  return (
    <div className="premium-panel overflow-hidden">
      <div className="border-b border-border bg-muted/20 p-6">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Report preview</p>
        <div className="mt-2 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Reports appear here after a run completes.</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Preview the report taxonomy with demo data, or upload a CSV to generate real executive, diagnostic, prediction, and decision reports.
            </p>
          </div>
          <Link href="/upload">
            <Button>
              <FileSpreadsheet className="mr-2 h-4 w-4" />
              Upload CSV
            </Button>
          </Link>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {sectors.map((sector) => (
            <Link
              key={sector}
              href={`/reports?demo=${sector}`}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                activeSector === sector ? "border-primary bg-primary/10 text-primary" : "border-border bg-card text-muted-foreground hover:text-foreground",
              )}
            >
              {sectorLabel[sector]}
            </Link>
          ))}
        </div>
      </div>
      <div className="grid gap-4 p-5 lg:grid-cols-4">
        {reportPreview.map((item) => (
          <div key={item.title} className="rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/35">
            <item.icon className="h-5 w-5 text-primary" />
            <p className="mt-4 text-sm font-semibold">{item.title}</p>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">{item.description}</p>
            <div className="mt-4 rounded-md border border-border bg-muted/25 p-3">
              <div className="h-2 w-2/3 rounded bg-muted-foreground/20" />
              <div className="mt-2 h-2 w-full rounded bg-muted-foreground/15" />
              <div className="mt-2 h-2 w-4/5 rounded bg-muted-foreground/15" />
            </div>
          </div>
        ))}
      </div>
      <div className="border-t border-border bg-muted/20 px-5 py-4 text-sm text-muted-foreground">
        Demo context: {sectorLabel[activeSector]} run, {run.recordCount.toLocaleString()} customers, {run.atRiskRate.toFixed(1)}% at risk.
      </div>
    </div>
  );
}

function ReportsPageInner() {
  const searchParams = useSearchParams();
  const demo = (searchParams.get("demo") as Sector | null) || null;
  const ctx = useExecutionContext();
  const workspace = useAnalysisWorkspace();
  const payload = workspace.payload;

  return (
    <PageShell>
      {workspace.error ? <ErrorBanner error={workspace.error} onRetry={() => workspace.refetch()} /> : null}
      <div className="premium-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">Reports</p>
            <h2 className="mt-2 max-w-3xl text-2xl font-semibold tracking-tight">
              Decision-ready reports attached to each churn analysis.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Review executive summaries, prediction evidence, diagnostics, and retention recommendations from the active workspace.
            </p>
          </div>
          <FileBarChart2 className="h-6 w-6 text-primary" />
        </div>
      </div>
      {!ctx.executionId ? (
        <ReportsPreview activeSector={demo && sectors.includes(demo) ? demo : ((ctx.sector as Sector) || "banking")} />
      ) : workspace.isLoading ? (
        <LoadingState label="Loading reports..." />
      ) : null}
      {payload ? (
        <SectionCard title="Report Explorer" description="Executive, diagnostic, prediction, and decision reports for the selected execution">
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

export default function ReportsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading reports..." />}>
      <ReportsPageInner />
    </Suspense>
  );
}
