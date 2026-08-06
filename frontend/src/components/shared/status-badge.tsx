import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { RoutingTier, StageStatus } from "@/lib/types";

const stageStatusStyles: Record<StageStatus, string> = {
  complete: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/35 dark:text-emerald-200 dark:border-emerald-900",
  running: "bg-sky-50 text-sky-800 border-sky-200 dark:bg-sky-950/35 dark:text-sky-200 dark:border-sky-900",
  pending: "bg-muted text-muted-foreground border-border",
  warning: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/35 dark:text-amber-200 dark:border-amber-900",
  failed: "bg-red-50 text-red-800 border-red-200 dark:bg-red-950/35 dark:text-red-200 dark:border-red-900",
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
  Green: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/35 dark:text-emerald-200 dark:border-emerald-900",
  Yellow: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/35 dark:text-amber-200 dark:border-amber-900",
  Red: "bg-red-50 text-red-800 border-red-200 dark:bg-red-950/35 dark:text-red-200 dark:border-red-900",
};

export function RoutingTierBadge({ tier, className }: { tier: RoutingTier; className?: string }) {
  return (
    <Badge variant="outline" className={cn("font-medium", routingTierStyles[tier], className)}>
      {tier}
    </Badge>
  );
}

const riskTierStyles: Record<string, string> = {
  Low: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/35 dark:text-emerald-200 dark:border-emerald-900",
  Medium: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/35 dark:text-amber-200 dark:border-amber-900",
  High: "bg-orange-50 text-orange-800 border-orange-200 dark:bg-orange-950/35 dark:text-orange-200 dark:border-orange-900",
  Critical: "bg-red-50 text-red-800 border-red-200 dark:bg-red-950/35 dark:text-red-200 dark:border-red-900",
};

export function RiskTierBadge({ tier, className }: { tier: string; className?: string }) {
  return (
    <Badge variant="outline" className={cn("font-medium", riskTierStyles[tier], className)}>
      {tier}
    </Badge>
  );
}
