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
  sparkline?: number[];
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
  sparkline,
  className,
}: MetricCardProps) {
  const DeltaIcon = deltaConfig[deltaDirection].icon;
  const points = sparkline?.length
    ? sparkline
        .map((value, index) => {
          const min = Math.min(...sparkline);
          const max = Math.max(...sparkline);
          const range = max - min || 1;
          const x = (index / Math.max(1, sparkline.length - 1)) * 88 + 6;
          const y = 34 - ((value - min) / range) * 24;
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ")
    : null;

  return (
    <Card className={cn("gap-3 py-4 transition-colors hover:ring-2 hover:ring-primary/20", className)}>
      <CardContent className="px-5">
        <div className="flex items-start justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
          {Icon ? (
            <span className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-muted/45">
              <Icon className="h-4 w-4 text-primary" />
            </span>
          ) : null}
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
        {points ? (
          <svg viewBox="0 0 100 40" className="mt-3 h-10 w-full text-primary" aria-hidden="true">
            <path d="M6 34 H94" className="stroke-border" strokeWidth="1" />
            <polyline
              points={points}
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : null}
      </CardContent>
    </Card>
  );
}
