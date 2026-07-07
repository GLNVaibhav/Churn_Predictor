import { api } from "@/lib/api/client";
import { PageShell } from "@/components/layout/page-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { SectionCard } from "@/components/shared/section-card";
import { StatusCard } from "@/components/shared/status-card";
import { ChurnTrendChart } from "@/components/charts/churn-trend-chart";
import { RecentRunsTable } from "@/components/dashboard/recent-runs-table";
import { StageStatusBadge } from "@/components/shared/status-badge";
import { Gauge, Percent, ShieldCheck, Sparkles } from "lucide-react";

const iconMap = {
  "total-predictions": Sparkles,
  "avg-churn-rate": Percent,
  "concept-confidence": Gauge,
  "routing-green": ShieldCheck,
};

export default async function DashboardPage() {
  const [stats, kpis, sectorHealth, churnTrend, recentRuns] = await Promise.all([
    api.dashboard.getStats(),
    api.dashboard.getKpis(),
    api.dashboard.getSectorHealth(),
    api.dashboard.getChurnTrend(),
    api.dashboard.getRecentRuns(),
  ]);

  return (
    <PageShell>
      <SectionCard
        title="Framework Intelligence Snapshot"
        description="Live indicators synthesized from the most recent execution across Coverage, Concept Confidence, Quality Gate, and Adaptive Routing"
        contentClassName="p-0"
      >
        <div className="grid grid-cols-2 divide-x divide-y divide-border/60 sm:grid-cols-3 xl:grid-cols-9 xl:divide-y-0">
          {kpis.map((kpi) => (
            <div key={kpi.id} className="flex flex-col gap-1 px-4 py-4">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                {kpi.label}
              </p>
              <p className="text-lg font-semibold tabular-nums leading-tight">{kpi.value}</p>
              {kpi.trendValue ? (
                <span
                  className={
                    kpi.trend === "up"
                      ? "text-[11px] text-emerald-400"
                      : kpi.trend === "down"
                        ? "text-[11px] text-red-400"
                        : "text-[11px] text-muted-foreground"
                  }
                >
                  {kpi.trendValue}
                </span>
              ) : kpi.description ? (
                <span className="text-[11px] text-muted-foreground">{kpi.description}</span>
              ) : null}
            </div>
          ))}
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <MetricCard
            key={stat.id}
            label={stat.label}
            value={stat.value}
            delta={stat.delta}
            deltaDirection={stat.deltaDirection}
            description={stat.description}
            icon={iconMap[stat.id as keyof typeof iconMap]}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <SectionCard
          title="Churn Rate Trend"
          description="7-day blended churn rate across sector models"
          className="xl:col-span-2"
        >
          <ChurnTrendChart data={churnTrend} />
        </SectionCard>

        <SectionCard title="Sector Health" description="Latest run status per sector" contentClassName="p-0">
          <div className="flex flex-col divide-y divide-border/60">
            {sectorHealth.map((sector) => (
              <div key={sector.sector} className="flex items-center justify-between px-5 py-3.5">
                <div>
                  <p className="text-sm font-medium">{sector.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {sector.totalRecords.toLocaleString()} records · {sector.avgConceptConfidence}% confidence
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold tabular-nums">{sector.churnRate}%</p>
                  <StageStatusBadge status={sector.status} className="mt-1" />
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        {sectorHealth.map((sector) => (
          <StatusCard
            key={sector.sector}
            title={sector.label}
            subtitle={`Last run ${new Date(sector.lastRunAt).toLocaleString()}`}
            status={sector.status}
            metrics={[
              { label: "Churn Rate", value: `${sector.churnRate}%` },
              { label: "Concept Confidence", value: `${sector.avgConceptConfidence}%` },
            ]}
          />
        ))}
      </div>

      <SectionCard title="Recent Prediction Runs" description="Most recent executions across the framework">
        <RecentRunsTable data={recentRuns} />
      </SectionCard>
    </PageShell>
  );
}
