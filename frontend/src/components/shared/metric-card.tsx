import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowDownRight, ArrowRight, ArrowUpRight, LucideIcon } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string;
  description?: string;
  delta?: string;
  deltaDirection?: "up" | "down" | "flat";
  icon?: LucideIcon;
  className?: string;
}

const deltaConfig = {
  up: { icon: ArrowUpRight, className: "text-emerald-400" },
  down: { icon: ArrowDownRight, className: "text-red-400" },
  flat: { icon: ArrowRight, className: "text-muted-foreground" },
};

export function MetricCard({
  label,
  value,
  description,
  delta,
  deltaDirection = "flat",
  icon: Icon,
  className,
}: MetricCardProps) {
  const DeltaIcon = deltaConfig[deltaDirection].icon;

  return (
    <Card className={cn("gap-3 py-5", className)}>
      <CardContent className="px-5">
        <div className="flex items-start justify-between">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          {Icon ? <Icon className="h-4 w-4 text-muted-foreground" /> : null}
        </div>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-semibold tracking-tight tabular-nums">{value}</span>
          {delta ? (
            <span className={cn("flex items-center gap-0.5 text-xs font-medium", deltaConfig[deltaDirection].className)}>
              <DeltaIcon className="h-3 w-3" />
              {delta}
            </span>
          ) : null}
        </div>
        {description ? (
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
