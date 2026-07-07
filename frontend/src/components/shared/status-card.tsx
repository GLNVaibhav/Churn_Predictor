import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { StageStatusBadge } from "@/components/shared/status-badge";
import type { StageStatus } from "@/lib/types";
import { LucideIcon } from "lucide-react";

interface StatusCardProps {
  title: string;
  subtitle?: string;
  status: StageStatus;
  icon?: LucideIcon;
  metrics?: { label: string; value: string }[];
  footer?: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export function StatusCard({
  title,
  subtitle,
  status,
  icon: Icon,
  metrics,
  footer,
  className,
  onClick,
}: StatusCardProps) {
  return (
    <Card
      onClick={onClick}
      className={cn(
        "gap-3 py-5 transition-colors",
        onClick && "cursor-pointer hover:border-primary/40 hover:bg-accent/40",
        className
      )}
    >
      <CardContent className="px-5">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            {Icon ? (
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted">
                <Icon className="h-4 w-4 text-foreground" />
              </div>
            ) : null}
            <div>
              <p className="text-sm font-semibold leading-none">{title}</p>
              {subtitle ? (
                <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
              ) : null}
            </div>
          </div>
          <StageStatusBadge status={status} />
        </div>
        {metrics && metrics.length > 0 ? (
          <div className="mt-4 grid grid-cols-2 gap-3 border-t border-border/60 pt-3">
            {metrics.map((m) => (
              <div key={m.label}>
                <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{m.label}</p>
                <p className="text-sm font-medium tabular-nums">{m.value}</p>
              </div>
            ))}
          </div>
        ) : null}
        {footer ? <div className="mt-3">{footer}</div> : null}
      </CardContent>
    </Card>
  );
}
