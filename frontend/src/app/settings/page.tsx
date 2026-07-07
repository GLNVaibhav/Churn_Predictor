import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

export default function SettingsPage() {
  return (
    <PageShell>
      <SectionCard title="API Configuration" description="Read-only frontend environment used by the live API client">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="api-endpoint">Backend API Endpoint</Label>
            <Input id="api-endpoint" defaultValue={process.env.NEXT_PUBLIC_API_URL || "Not configured"} disabled />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="default-mode">Default Prediction Mode</Label>
            <Input id="default-mode" defaultValue="auto" disabled />
          </div>
        </div>
        <Separator className="my-5" />
        <p className="text-xs text-muted-foreground">
          Update NEXT_PUBLIC_API_URL to point the frontend at a different FastAPI backend.
        </p>
      </SectionCard>
    </PageShell>
  );
}
