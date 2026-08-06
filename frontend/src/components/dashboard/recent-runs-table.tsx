"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { RiskTierBadge, StageStatusBadge } from "@/components/shared/status-badge";
import type { RecentRun, Sector } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ArrowRight, UploadCloud } from "lucide-react";

export type DashboardRun = RecentRun & {
  avgRisk: number;
  atRiskRate: number;
  topDriver: string;
  semanticStatus: "Ready" | "Review" | "Weak";
};

const sectorLabel: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  healthcare: "Healthcare",
  ecommerce: "E-commerce",
};

const demoRuns: DashboardRun[] = [
  {
    id: "demo-banking-550",
    sector: "banking",
    mode: "Auto",
    routingTier: "Green",
    recordCount: 550,
    churnDetected: 394,
    avgRisk: 69.5,
    atRiskRate: 71.6,
    topDriver: "Low engagement",
    semanticStatus: "Ready",
    submittedAt: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
    status: "complete",
  },
  {
    id: "demo-telecom-450",
    sector: "telecom",
    mode: "Auto",
    routingTier: "Yellow",
    recordCount: 450,
    churnDetected: 126,
    avgRisk: 42.8,
    atRiskRate: 28,
    topDriver: "Contract expiry",
    semanticStatus: "Review",
    submittedAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    status: "complete",
  },
  {
    id: "demo-ecommerce-600",
    sector: "ecommerce",
    mode: "Auto",
    routingTier: "Green",
    recordCount: 600,
    churnDetected: 148,
    avgRisk: 31.2,
    atRiskRate: 24.7,
    topDriver: "Purchase inactivity",
    semanticStatus: "Ready",
    submittedAt: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    status: "complete",
  },
  {
    id: "demo-healthcare-320",
    sector: "healthcare",
    mode: "Auto",
    routingTier: "Yellow",
    recordCount: 320,
    churnDetected: 52,
    avgRisk: 24.4,
    atRiskRate: 16.3,
    topDriver: "Appointment gaps",
    semanticStatus: "Review",
    submittedAt: new Date(Date.now() - 1000 * 60 * 60 * 31).toISOString(),
    status: "complete",
  },
];

export function demoRunForSector(sector: Sector) {
  return demoRuns.find((run) => run.sector === sector) || demoRuns[0];
}

function relativeTime(value: string) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "Unknown";
  const diff = Date.now() - timestamp;
  const minutes = Math.max(1, Math.round(diff / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function semanticClass(status: DashboardRun["semanticStatus"]) {
  if (status === "Ready") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "Review") return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-red-200 bg-red-50 text-red-800";
}

function riskTier(avgRisk: number) {
  if (avgRisk >= 70) return "Critical";
  if (avgRisk >= 50) return "High";
  if (avgRisk >= 30) return "Medium";
  return "Low";
}

export function RecentRunsTable({
  data,
  onRestore,
}: {
  data: DashboardRun[];
  onRestore?: (row: DashboardRun) => void;
}) {
  const [selected, setSelected] = useState<DashboardRun | null>(null);
  const rows = useMemo(() => data, [data]);

  function openRow(row: DashboardRun) {
    setSelected(row);
    onRestore?.(row);
  }

  return (
    <>
      <div className="overflow-x-auto rounded-lg border border-border/70">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="border-b border-border bg-muted/35 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Run</th>
              <th className="px-4 py-3">Industry</th>
              <th className="px-4 py-3 text-right">At-risk</th>
              <th className="px-4 py-3">Avg risk</th>
              <th className="px-4 py-3">Top driver</th>
              <th className="px-4 py-3">Semantic</th>
              <th className="px-4 py-3">Updated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                onClick={() => openRow(row)}
                className="cursor-pointer border-b border-border/60 transition-colors last:border-b-0 hover:bg-muted/35"
              >
                <td className="px-4 py-3">
                  <div className="font-mono text-xs">{row.id}</div>
                  <div className="mt-1 flex items-center gap-2">
                    <StageStatusBadge status={row.status} />
                    <span className="text-xs text-muted-foreground">{row.recordCount.toLocaleString()} customers</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="rounded-full border border-border bg-background px-2.5 py-1 text-xs font-medium">
                    {sectorLabel[row.sector]}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-semibold tabular-nums">
                  {row.atRiskRate.toFixed(1)}%
                  <div className="text-xs font-normal text-muted-foreground">{row.churnDetected.toLocaleString()} customers</div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="h-2 w-28 rounded-full bg-muted">
                      <div className="h-2 rounded-full bg-red-200" style={{ width: `${Math.min(100, row.avgRisk)}%` }} />
                    </div>
                    <span className="w-12 text-right font-semibold tabular-nums">{row.avgRisk.toFixed(1)}%</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{row.topDriver}</td>
                <td className="px-4 py-3">
                  <span className={cn("rounded-full border px-2.5 py-1 text-xs font-medium", semanticClass(row.semanticStatus))}>
                    {row.semanticStatus}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{relativeTime(row.submittedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Sheet open={Boolean(selected)} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent className="overflow-y-auto sm:max-w-xl">
          {selected ? (
            <>
              <SheetHeader>
                <SheetTitle>{sectorLabel[selected.sector]} analysis</SheetTitle>
                <SheetDescription>{selected.recordCount.toLocaleString()} customers analyzed - {relativeTime(selected.submittedAt)}</SheetDescription>
              </SheetHeader>
              <div className="space-y-4 px-4 pb-6">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-border bg-background p-4">
                    <p className="text-xs text-muted-foreground">At-risk customers</p>
                    <p className="mt-1 text-2xl font-semibold tabular-nums">{selected.churnDetected.toLocaleString()}</p>
                  </div>
                  <div className="rounded-lg border border-border bg-background p-4">
                    <p className="text-xs text-muted-foreground">Average risk</p>
                    <p className="mt-1 text-2xl font-semibold tabular-nums">{selected.avgRisk.toFixed(1)}%</p>
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-background p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Top driver</p>
                  <p className="mt-2 text-sm font-medium">{selected.topDriver}</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Open the workspace to inspect prediction evidence, ABIL context signals, semantic status, and decision support for this run.
                  </p>
                </div>
                <div className="flex items-center justify-between rounded-lg border border-border bg-background p-4">
                  <span className="text-sm text-muted-foreground">Risk tier</span>
                  <RiskTierBadge tier={riskTier(selected.avgRisk)} />
                </div>
                <Link href="/workspace">
                  <Button className="w-full">
                    Open workspace
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </>
  );
}

export function RecentRunsEmptyState({ onLoadDemo }: { onLoadDemo: (sector: Sector) => void }) {
  return (
    <div className="rounded-lg border border-border bg-background p-6">
      <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-center">
        <div>
          <p className="text-base font-semibold">No analyses yet</p>
          <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
            Upload a customer CSV to create your first churn workspace, or load a demo run to inspect the dashboard interaction model.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {(["telecom", "banking", "ecommerce", "healthcare"] as Sector[]).map((sector) => (
              <button
                key={sector}
                type="button"
                onClick={() => onLoadDemo(sector)}
                className="rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:border-primary/40 hover:text-primary"
              >
                {sectorLabel[sector]}
              </button>
            ))}
          </div>
        </div>
        <Link href="/upload">
          <Button className="w-full lg:w-auto">
            <UploadCloud className="mr-2 h-4 w-4" />
            Upload CSV
          </Button>
        </Link>
      </div>
    </div>
  );
}
