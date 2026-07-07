import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { RoutingTier, StageStatus } from "@/lib/types";

const stageStatusStyles: Record<StageStatus, string> = {
  complete: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  running: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  pending: "bg-muted text-muted-foreground border-border",
  warning: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
};

const stageStatusLabel: Record<StageStatus, string> = {
  complete: "Complete",
  running: "Running",
  pending: "Pending",
  warning: "Warning",
  failed: "Failed",
};

export function StageStatusBadge({ status, className }: { status: StageStatus; className?: string }) {
  return (
    <Badge
      variant="outline"
      className={cn("font-medium capitalize", stageStatusStyles[status], className)}
    >
      {stageStatusLabel[status]}
    </Badge>
  );
}

const routingTierStyles: Record<RoutingTier, string> = {
  Green: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  Yellow: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  Red: "bg-red-500/10 text-red-400 border-red-500/20",
};

export function RoutingTierBadge({ tier, className }: { tier: RoutingTier; className?: string }) {
  return (
    <Badge variant="outline" className={cn("font-medium", routingTierStyles[tier], className)}>
      {tier}
    </Badge>
  );
}

const riskTierStyles: Record<string, string> = {
  Low: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  Medium: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  High: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  Critical: "bg-red-500/10 text-red-400 border-red-500/20",
};

export function RiskTierBadge({ tier, className }: { tier: string; className?: string }) {
  return (
    <Badge variant="outline" className={cn("font-medium", riskTierStyles[tier], className)}>
      {tier}
    </Badge>
  );
}
