"use client";

import { DataTable, DataTableColumn } from "@/components/shared/data-table";
import { RoutingTierBadge, StageStatusBadge } from "@/components/shared/status-badge";
import type { RecentRun } from "@/lib/types";

const sectorLabel: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  healthcare: "Healthcare",
  ecommerce: "E-commerce",
};

const columns: DataTableColumn<RecentRun>[] = [
  {
    key: "id",
    header: "Run ID",
    render: (row) => <span className="font-mono text-xs">{row.id}</span>,
  },
  {
    key: "sector",
    header: "Sector",
    render: (row) => sectorLabel[row.sector],
    sortValue: (row) => row.sector,
  },
  {
    key: "mode",
    header: "Mode",
    render: (row) => row.mode,
    sortValue: (row) => row.mode,
  },
  {
    key: "routingTier",
    header: "Routing",
    render: (row) => <RoutingTierBadge tier={row.routingTier} />,
  },
  {
    key: "recordCount",
    header: "Records",
    align: "right",
    render: (row) => row.recordCount.toLocaleString(),
    sortValue: (row) => row.recordCount,
  },
  {
    key: "churnDetected",
    header: "Churn Detected",
    align: "right",
    render: (row) => row.churnDetected.toLocaleString(),
    sortValue: (row) => row.churnDetected,
  },
  {
    key: "status",
    header: "Status",
    render: (row) => <StageStatusBadge status={row.status} />,
  },
];

export function RecentRunsTable({ data, onRestore }: { data: RecentRun[]; onRestore?: (row: RecentRun) => void }) {
  return <DataTable columns={columns} data={data} rowKey={(row) => row.id} onRowClick={onRestore} />;
}
