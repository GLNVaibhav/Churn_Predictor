import { api } from "@/lib/api/client";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

const sectorLabel: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  healthcare: "Healthcare",
  ecommerce: "E-commerce",
};

export default async function SettingsPage() {
  const sectorConfigs = await api.settings.getSectorConfigs();

  return (
    <PageShell>
      <SectionCard
        title="Sector Model Registry"
        description="Read-only view of trained sector models and target configuration"
        contentClassName="p-0"
      >
        <div className="flex flex-col divide-y divide-border/60">
          {sectorConfigs.map((cfg) => (
            <div key={cfg.sector} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
              <div>
                <p className="text-sm font-medium">{sectorLabel[cfg.sector]}</p>
                <p className="mt-0.5 font-mono text-xs text-muted-foreground">{cfg.modelPath}</p>
              </div>
              <div className="flex items-center gap-6">
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">Target column</p>
                  <p className="text-sm font-medium">{cfg.targetCol}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">Green / Yellow thresholds</p>
                  <p className="text-sm font-medium tabular-nums">
                    {cfg.routingThresholdGreen} / {cfg.routingThresholdYellow}
                  </p>
                </div>
                <Badge
                  variant="outline"
                  className={
                    cfg.trained
                      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                      : "border-muted text-muted-foreground"
                  }
                >
                  {cfg.trained ? "Trained" : "Not Trained"}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Platform Preferences" description="Placeholder settings — not yet wired to a backend">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="api-endpoint">Backend API Endpoint</Label>
            <Input id="api-endpoint" placeholder="http://localhost:8000 (FastAPI — Phase 2)" disabled />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="default-mode">Default Prediction Mode</Label>
            <Input id="default-mode" defaultValue="auto" disabled />
          </div>
        </div>
        <Separator className="my-5" />
        <p className="text-xs text-muted-foreground">
          These fields are placeholders for Phase 2, when the frontend connects to the FastAPI service
          fronting the existing CLI pipeline.
        </p>
      </SectionCard>
    </PageShell>
  );
}
