"use client";

import { useMemo, useState } from "react";
import { DataTable, DataTableColumn } from "@/components/shared/data-table";
import { RiskTierBadge, RoutingTierBadge } from "@/components/shared/status-badge";
import { PredictionDetailSheet } from "@/components/predictions/prediction-detail-sheet";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import type { PredictionRecord } from "@/lib/types";

const sectorLabel: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  healthcare: "Healthcare",
  ecommerce: "E-commerce",
};

const PAGE_SIZE = 8;

const columns: DataTableColumn<PredictionRecord>[] = [
  {
    key: "customerId",
    header: "Customer ID",
    render: (row) => <span className="font-mono text-xs">{row.customerId}</span>,
    sortValue: (row) => row.customerId,
  },
  {
    key: "sector",
    header: "Sector",
    render: (row) => sectorLabel[row.sector],
    sortValue: (row) => row.sector,
  },
  {
    key: "churnProbability",
    header: "Churn Probability",
    align: "right",
    render: (row) => {
      const value = row.churnProbability * 100;
      return (
        <div className="ml-auto w-32">
          <div className="mb-1 flex justify-end text-xs font-semibold tabular-nums">{value.toFixed(1)}%</div>
          <div className="h-2 rounded-full bg-muted">
            <div
              className="h-2 rounded-full bg-red-200"
              style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
            />
          </div>
        </div>
      );
    },
    sortValue: (row) => row.churnProbability,
  },
  {
    key: "riskTier",
    header: "Risk Tier",
    render: (row) => <RiskTierBadge tier={row.riskTier} />,
    sortValue: (row) => row.riskTier,
  },
  {
    key: "routingTier",
    header: "Routing",
    render: (row) => <RoutingTierBadge tier={row.routingTier} />,
  },
  {
    key: "selectedModel",
    header: "Selected Model",
    render: (row) => (
      <span className="text-xs text-muted-foreground">{row.selectedModel.replaceAll("_", " ")}</span>
    ),
  },
  {
    key: "decision",
    header: "Decision",
    render: (row) => <span className="text-xs font-medium">{row.decision}</span>,
    sortValue: (row) => row.decision,
  },
  {
    key: "predictedAt",
    header: "Predicted At",
    render: (row) => (
      <span className="text-xs text-muted-foreground">
        {new Date(row.predictedAt).toLocaleString()}
      </span>
    ),
    sortValue: (row) => row.predictedAt,
  },
];

export function PredictionsTable({ data }: { data: PredictionRecord[] }) {
  const [search, setSearch] = useState("");
  const [sectorFilter, setSectorFilter] = useState<string>("all");
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<PredictionRecord | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const filtered = useMemo(() => {
    return data.filter((row) => {
      const matchesSearch = row.customerId.toLowerCase().includes(search.toLowerCase());
      const matchesSector = sectorFilter === "all" || row.sector === sectorFilter;
      const matchesRisk = riskFilter === "all" || row.riskTier === riskFilter;
      return matchesSearch && matchesSector && matchesRisk;
    });
  }, [data, search, sectorFilter, riskFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageData = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const highRiskCount = filtered.filter((row) => row.riskTier === "High" || row.riskTier === "Critical").length;
  const avgRisk = filtered.length ? filtered.reduce((sum, row) => sum + row.churnProbability, 0) / filtered.length : 0;
  const escalationCount = filtered.filter((row) => row.decision === "Escalate").length;

  function handleRowClick(row: PredictionRecord) {
    setSelected(row);
    setSheetOpen(true);
  }

  function updateFilter(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ["High-risk customers", highRiskCount.toLocaleString(), "Priority cohort"],
          ["Average risk", `${(avgRisk * 100).toFixed(1)}%`, "Filtered view"],
          ["Escalations", escalationCount.toLocaleString(), "Need action"],
        ].map(([label, value, hint]) => (
          <div key={label} className="rounded-md border border-border/60 bg-background/75 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
          </div>
        ))}
      </div>
      {filtered.length > 0 && highRiskCount === 0 ? (
        <div className="rounded-lg border border-emerald-500/25 bg-emerald-50 p-4 text-sm text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200">
          <p className="font-semibold">Rock-solid retention in this filtered cohort.</p>
          <p className="mt-1 text-xs leading-5 opacity-80">No high or critical churn risk customers are currently visible in this view.</p>
        </div>
      ) : null}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search customer ID..."
            value={search}
            onChange={(e) => updateFilter(setSearch, e.target.value)}
            className="pl-8"
          />
        </div>
        <div className="flex gap-2">
          <Select value={sectorFilter} onValueChange={(v) => updateFilter(setSectorFilter, v as string)}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Sector" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Sectors</SelectItem>
              <SelectItem value="telecom">Telecom</SelectItem>
              <SelectItem value="banking">Banking</SelectItem>
              <SelectItem value="healthcare">Healthcare</SelectItem>
              <SelectItem value="ecommerce">E-commerce</SelectItem>
            </SelectContent>
          </Select>
          <Select value={riskFilter} onValueChange={(v) => updateFilter(setRiskFilter, v as string)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Risk Tier" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Risk Tiers</SelectItem>
              <SelectItem value="Low">Low</SelectItem>
              <SelectItem value="Medium">Medium</SelectItem>
              <SelectItem value="High">High</SelectItem>
              <SelectItem value="Critical">Critical</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={pageData}
        rowKey={(row) => row.id}
        onRowClick={handleRowClick}
        emptyLabel="No matching customers. Adjust filters or open a different analysis."
      />

      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          Showing {pageData.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1}–
          {(currentPage - 1) * PAGE_SIZE + pageData.length} of {filtered.length} records
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Prev
          </Button>
          <span className="text-xs text-muted-foreground">
            Page {currentPage} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
          >
            Next
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <PredictionDetailSheet record={selected} open={sheetOpen} onOpenChange={setSheetOpen} />
    </div>
  );
}
