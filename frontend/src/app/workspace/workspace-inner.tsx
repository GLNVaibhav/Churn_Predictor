"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { WorkspaceSectionView } from "@/components/workspace/workspace-sections";
import { Button } from "@/components/ui/button";
import { useAnalysisWorkspace } from "@/lib/hooks/use-analysis-workspace";
import { WORKSPACE_SECTIONS, type WorkspaceSection } from "@/lib/navigation";
import { useExecutionContext } from "@/lib/context/execution-context";
import { demoRunForSector } from "@/components/dashboard/recent-runs-table";
import type { Sector } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ArrowRight, BarChart3, CheckCircle2, FileSpreadsheet, PlusCircle, ShieldAlert } from "lucide-react";

const sectors: Sector[] = ["telecom", "banking", "ecommerce", "healthcare"];
const sectorLabel: Record<Sector, string> = {
  telecom: "Telecom",
  banking: "Banking",
  ecommerce: "E-commerce",
  healthcare: "Healthcare",
};

function WorkspacePreview({ activeSector }: { activeSector: Sector }) {
  const run = demoRunForSector(activeSector);
  return (
    <div className="premium-panel overflow-hidden">
      <div className="border-b border-border bg-muted/20 p-6">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Analysis workspace preview</p>
        <div className="mt-2 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Load a demo run or upload your own CSV.</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              The workspace will hold the analysis output: prediction cohorts, semantic evidence, comparison, reports, and decision support.
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
              href={`/workspace?demo=${sector}`}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                sector === activeSector ? "border-primary bg-primary/10 text-primary" : "border-border bg-card text-muted-foreground hover:text-foreground",
              )}
            >
              {sectorLabel[sector]}
            </Link>
          ))}
        </div>
      </div>
      <div className="grid gap-0 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="border-b border-border p-5 lg:border-b-0 lg:border-r">
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Demo run</p>
            <p className="mt-2 text-lg font-semibold">{sectorLabel[activeSector]}</p>
            <div className="mt-4 grid gap-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Customers</span>
                <span className="font-semibold tabular-nums">{run.recordCount.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">At risk</span>
                <span className="font-semibold tabular-nums">{run.atRiskRate.toFixed(1)}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Top driver</span>
                <span className="font-medium">{run.topDriver}</span>
              </div>
            </div>
          </div>
          <Link href={`/reports?demo=${activeSector}`}>
            <Button variant="outline" className="mt-3 w-full">
              Preview reports
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
        <div className="p-5">
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: "Prediction", value: `${run.avgRisk.toFixed(1)}%`, Icon: BarChart3 },
              { label: "Evidence", value: run.semanticStatus, Icon: CheckCircle2 },
              { label: "Decision", value: run.avgRisk > 50 ? "Escalate" : "Monitor", Icon: ShieldAlert },
            ].map(({ label, value, Icon }) => (
              <div key={label} className="rounded-lg border border-border bg-background p-4">
                <Icon className="h-4 w-4 text-primary" />
                <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
                <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 overflow-hidden rounded-lg border border-border">
            <div className="grid grid-cols-[1fr_120px_120px] border-b border-border bg-muted/35 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <span>Cohort</span>
              <span>Risk</span>
              <span>Status</span>
            </div>
            {[
              ["Dormant premium customers", run.avgRisk],
              ["Low engagement cohort", Math.max(18, run.avgRisk - 14)],
              ["Recently active customers", Math.max(8, run.avgRisk - 31)],
            ].map(([label, risk]) => (
              <div key={String(label)} className="grid grid-cols-[1fr_120px_120px] items-center border-b border-border/60 px-4 py-3 text-sm last:border-b-0">
                <span className="font-medium">{label}</span>
                <span className="tabular-nums">{Number(risk).toFixed(1)}%</span>
                <span className="w-fit rounded-full border border-red-200 bg-red-50 px-2 py-1 text-xs font-medium text-red-800">At risk</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function WorkspacePageInner() {
  const searchParams = useSearchParams();
  const tab = (searchParams.get("tab") as WorkspaceSection) || "overview";
  const demo = (searchParams.get("demo") as Sector | null) || null;
  const ctx = useExecutionContext();
  const workspace = useAnalysisWorkspace();

  return (
    <PageShell>
      {workspace.error ? (
        <ErrorBanner error={workspace.error} onRetry={() => workspace.refetch()} />
      ) : null}

      {!ctx.executionId ? (
        <WorkspacePreview activeSector={demo && sectors.includes(demo) ? demo : ((ctx.sector as Sector) || "banking")} />
      ) : workspace.isLoading ? (
        <LoadingState label="Loading analysis workspace..." />
      ) : null}

      {ctx.executionId && workspace.payload ? (
        <>
          <div className="premium-panel p-3">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3 px-1">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-primary">Analysis workspace</p>
                <p className="mt-1 text-sm text-muted-foreground">Predictions, explanations, reports, comparison, and run evidence.</p>
              </div>
              <Link href="/upload">
                <Button variant="outline" size="sm">
                  <PlusCircle className="mr-2 h-4 w-4" />
                  New Run
                </Button>
              </Link>
            </div>
            <div className="flex flex-wrap gap-1 rounded-md bg-muted/45 p-1">
              {WORKSPACE_SECTIONS.map((section) => (
                <Link
                  key={section.id}
                  href={`/workspace?tab=${section.id}`}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                    tab === section.id
                      ? "bg-card text-foreground shadow-sm ring-1 ring-border/70"
                      : "text-muted-foreground hover:bg-background/70 hover:text-foreground"
                  )}
                >
                  {section.label}
                </Link>
              ))}
            </div>
          </div>
          <WorkspaceSectionView section={tab} data={workspace} />
        </>
      ) : null}
    </PageShell>
  );
}
