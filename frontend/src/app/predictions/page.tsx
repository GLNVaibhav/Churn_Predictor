import { api } from "@/lib/api/client";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { MetricCard } from "@/components/shared/metric-card";
import { PredictionsTable } from "@/components/predictions/predictions-table";
import { AlertTriangle, Percent, Sparkles, Users } from "lucide-react";

export default async function PredictionsPage() {
  const predictions = await api.predictions.getAll();
  const avgProbability =
    predictions.reduce((sum, p) => sum + p.churnProbability, 0) / predictions.length;
  const critical = predictions.filter((p) => p.riskTier === "Critical").length;
  const refused = predictions.filter((p) => p.routingTier === "Red").length;

  return (
    <PageShell>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Total Records" value={`${predictions.length}`} icon={Users} description="Across all sectors" />
        <MetricCard
          label="Avg. Churn Probability"
          value={`${(avgProbability * 100).toFixed(1)}%`}
          icon={Percent}
        />
        <MetricCard label="Critical Risk" value={`${critical}`} icon={AlertTriangle} description="Requires immediate attention" />
        <MetricCard label="Refused Predictions" value={`${refused}`} icon={Sparkles} description="Red routing tier — quality gate failed" />
      </div>

      <SectionCard title="Scored Records" description="All predictions produced by the framework, sortable by any column">
        <PredictionsTable data={predictions} />
      </SectionCard>
    </PageShell>
  );
}
