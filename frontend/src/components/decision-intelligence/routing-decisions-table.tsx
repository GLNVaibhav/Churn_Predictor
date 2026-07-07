"use client";

import { DataTable, DataTableColumn } from "@/components/shared/data-table";
import { RoutingTierBadge } from "@/components/shared/status-badge";
import type { RoutingDecisionSummary } from "@/lib/types";

const sectorLabel: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  healthcare: "Healthcare",
  ecommerce: "E-commerce",
};

const columns: DataTableColumn<RoutingDecisionSummary>[] = [
  {
    key: "sector",
    header: "Sector",
    render: (row) => sectorLabel[row.sector],
    sortValue: (row) => row.sector,
  },
  {
    key: "tier",
    header: "Routing Tier",
    render: (row) => <RoutingTierBadge tier={row.tier} />,
    sortValue: (row) => row.tier,
  },
  {
    key: "selectedModel",
    header: "Selected Model",
    render: (row) => (
      <span className="text-xs text-muted-foreground">{row.selectedModel.replaceAll("_", " ")}</span>
    ),
  },
  {
    key: "coverageScore",
    header: "Coverage",
    align: "right",
    render: (row) => `${row.coverageScore}%`,
    sortValue: (row) => row.coverageScore,
  },
  {
    key: "qualityScore",
    header: "Quality Score",
    align: "right",
    render: (row) => row.qualityScore,
    sortValue: (row) => row.qualityScore,
  },
  {
    key: "conceptConfidence",
    header: "Concept Confidence",
    align: "right",
    render: (row) => `${row.conceptConfidence}%`,
    sortValue: (row) => row.conceptConfidence,
  },
  {
    key: "reason",
    header: "Routing Reason",
    render: (row) => <span className="text-xs text-muted-foreground">{row.reason}</span>,
  },
];

export function RoutingDecisionsTable({ data }: { data: RoutingDecisionSummary[] }) {
  return <DataTable columns={columns} data={data} rowKey={(row) => `${row.sector}-${row.timestamp}`} />;
}
