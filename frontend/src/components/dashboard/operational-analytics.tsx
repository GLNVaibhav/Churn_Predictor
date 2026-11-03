"use client";

import { useMemo } from "react";
import AreaChart, { Area } from "@/components/charts/area-chart";
import BarChart from "@/components/charts/bar-chart";
import { Bar } from "@/components/charts/bar";
import { Grid } from "@/components/charts/grid";
import RingChart from "@/components/charts/ring-chart";
import { Ring } from "@/components/charts/ring";
import { RingCenter } from "@/components/charts/ring-center";
import { XAxis } from "@/components/charts/x-axis";
import { BarXAxis } from "@/components/charts/bar-x-axis";
import { ChartTooltip } from "@/components/charts/tooltip/chart-tooltip";
import type { ExecutionSummaryResponse } from "@/lib/api/executions";
import { sectorLabel } from "@/lib/constants/sectors";

const statusColors: Record<string, string> = {
  Succeeded: "var(--chart-1)",
  Running: "var(--chart-2)",
  Pending: "var(--chart-3)",
  Failed: "var(--destructive)",
  Cancelled: "var(--muted-foreground)",
  "Other / not reported": "var(--chart-4)",
};

function statusGroup(status?: string | null) {
  const value = status?.trim().toUpperCase();
  if (["SUCCEEDED", "SUCCESS", "COMPLETE", "COMPLETED"].includes(value || "")) return "Succeeded";
  if (value === "RUNNING") return "Running";
  if (value === "PENDING") return "Pending";
  if (value === "FAILED") return "Failed";
  if (value === "CANCELLED") return "Cancelled";
  return "Other / not reported";
}

function useExecutionCharts(executions: ExecutionSummaryResponse[]) {
  return useMemo(() => {
    const byDay = new Map<string, { day: string; executions: number }>();
    const byStatus = new Map<string, number>();
    const bySector = new Map<string, number>();

    for (const execution of executions) {
      const date = [execution.created_at, execution.started_at]
        .filter((value): value is string => Boolean(value))
        .map((value) => new Date(value))
        .find((value) => Number.isFinite(value.getTime()));
      if (date) {
        const day = date.toISOString().slice(0, 10);
        const current = byDay.get(day) || { day, executions: 0 };
        current.executions += 1;
        byDay.set(day, current);
      }

      const status = statusGroup(execution.status);
      byStatus.set(status, (byStatus.get(status) || 0) + 1);
      const sector = sectorLabel(execution.sector || "Sector not reported");
      bySector.set(sector, (bySector.get(sector) || 0) + 1);
    }

    const trend = [...byDay.values()].sort((left, right) => left.day.localeCompare(right.day)).slice(-14);
    const statuses = [...byStatus.entries()].map(([name, value]) => ({ name, value }));
    const sectors = [...bySector.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name));

    return { trend, statuses, sectors };
  }, [executions]);
}

function ChartEmptyState({ children }: { children: string }) {
  return (
    <div className="flex h-[220px] items-center justify-center rounded-xl border border-dashed border-border bg-muted/20 px-6 text-center">
      <p className="max-w-sm text-xs leading-5 text-muted-foreground">{children}</p>
    </div>
  );
}

export function ExecutionAnalytics({ executions }: { executions: ExecutionSummaryResponse[] }) {
  const { trend, statuses } = useExecutionCharts(executions);
  const total = statuses.reduce((sum, item) => sum + item.value, 0);
  const ringData = statuses.map((item) => ({
    label: item.name,
    value: item.value,
    maxValue: Math.max(total, 1),
    color: statusColors[item.name],
  }));
  const trendData = trend.map((item) => ({ date: new Date(`${item.day}T00:00:00Z`), executions: item.executions }));

  return (
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(280px,.85fr)]">
      <section className="min-w-0 rounded-2xl border border-border/80 bg-card p-4 shadow-[var(--shadow-card)] sm:p-5" aria-labelledby="execution-trend-title">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted-foreground">Activity over time</p>
            <h3 id="execution-trend-title" className="mt-1 text-sm font-semibold">Execution history</h3>
          </div>
          <span className="rounded-full border border-border bg-muted/50 px-2.5 py-1 text-[10px] text-muted-foreground">Latest 14 observed dates · UTC</span>
        </div>
        {trendData.length ? (
          <AreaChart data={trendData} xDataKey="date" aspectRatio="2.45 / 1" margin={{ top: 18, right: 12, bottom: 26, left: 16 }} className="mt-3" animationDuration={760}>
            <Grid horizontal />
            <Area dataKey="executions" fill="var(--chart-line-primary)" fillOpacity={0.3} gradientToOpacity={0.015} stroke="var(--chart-line-primary)" showMarkers />
            <XAxis />
            <ChartTooltip />
          </AreaChart>
        ) : (
          <ChartEmptyState>Execution activity will appear when the history API returns timestamped records.</ChartEmptyState>
        )}
        <ul className="sr-only" aria-label="Execution history data">
          {trend.map((item) => <li key={item.day}>{item.day}: {item.executions} execution records</li>)}
        </ul>
      </section>

      <section className="min-w-0 rounded-2xl border border-border/80 bg-card p-4 shadow-[var(--shadow-card)] sm:p-5" aria-labelledby="execution-status-title">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted-foreground">Current history snapshot</p>
            <h3 id="execution-status-title" className="mt-1 text-sm font-semibold">Execution status mix</h3>
          </div>
          <span className="text-xs tabular-nums text-muted-foreground">{total.toLocaleString()} records</span>
        </div>
        {ringData.length ? (
          <div className="mt-2 grid grid-cols-1 items-center gap-1 sm:grid-cols-[minmax(190px,.9fr)_minmax(0,1fr)] sm:gap-3 xl:grid-cols-1 2xl:grid-cols-[minmax(190px,.9fr)_minmax(0,1fr)]">
            <RingChart data={ringData} size={190} strokeWidth={7} ringGap={3} baseInnerRadius={26} padding={6} className="mx-auto w-full max-w-[190px]">
              {ringData.map((item, index) => <Ring key={item.label} index={index} color={item.color} showGlow={false} />)}
              <RingCenter defaultLabel="execution records" />
            </RingChart>
            <ul className="space-y-2 text-xs" aria-label="Execution records by status">
              {statuses.map((item) => (
                <li key={item.name} className="flex min-w-0 items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: statusColors[item.name] }} aria-hidden="true" />
                    <span className="truncate text-muted-foreground">{item.name}</span>
                  </span>
                  <span className="font-semibold tabular-nums">{item.value.toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ChartEmptyState>No execution status records are available to chart.</ChartEmptyState>
        )}
        <p className="mt-2 text-[10px] leading-4 text-muted-foreground">Execution states only; this is not a churn or prediction distribution.</p>
      </section>
    </div>
  );
}

export function SectorExecutionChart({ executions }: { executions: ExecutionSummaryResponse[] }) {
  const { sectors } = useExecutionCharts(executions);
  const data = sectors.map(({ name, count }) => ({ name, count }));

  if (!data.length) {
    return <ChartEmptyState>Sector comparisons will appear when returned execution records include sector data.</ChartEmptyState>;
  }

  return (
    <div className="min-w-0">
      <BarChart data={data} xDataKey="name" aspectRatio="2.3 / 1" margin={{ top: 18, right: 12, bottom: 26, left: 12 }} animationDuration={700}>
        <Grid horizontal />
        <Bar dataKey="count" fill="var(--chart-line-primary)" lineCap={5} showValue animate />
        <BarXAxis showAllLabels maxLabels={8} />
        <ChartTooltip />
      </BarChart>
      <p className="mt-1 text-[10px] text-muted-foreground">Execution records only; counts do not indicate sector performance.</p>
      <ul className="sr-only" aria-label="Execution records by sector">
        {sectors.map((sector) => <li key={sector.name}>{sector.name}: {sector.count} execution records</li>)}
      </ul>
    </div>
  );
}
