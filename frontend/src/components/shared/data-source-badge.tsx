import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type DataSourceKind = "live" | "demonstration" | "sample" | "historical" | "available" | "degraded" | "unavailable" | "loading" | "failed" | "unknown" | "unverified";

const sourcePresentation: Record<DataSourceKind, { label: string; className: string }> = {
  live: { label: "Live data", className: "border-success/35 bg-success/10 text-success" },
  demonstration: { label: "Demonstration", className: "border-warning/40 bg-warning/10 text-warning" },
  sample: { label: "Sample content", className: "border-info/35 bg-info/10 text-info" },
  historical: { label: "Historical", className: "border-border bg-muted text-muted-foreground" },
  available: { label: "Available", className: "border-success/35 bg-success/10 text-success" },
  degraded: { label: "Degraded", className: "border-warning/40 bg-warning/10 text-warning" },
  unavailable: { label: "Unavailable", className: "border-destructive/30 bg-destructive/10 text-destructive" },
  loading: { label: "Checking", className: "border-info/35 bg-info/10 text-info" },
  failed: { label: "Request failed", className: "border-destructive/35 bg-destructive/10 text-destructive" },
  unknown: { label: "Unknown", className: "border-border bg-muted text-muted-foreground" },
  unverified: { label: "Unverified", className: "border-warning/40 bg-warning/10 text-warning" },
};

export function DataSourceBadge({
  kind,
  label,
  className,
}: {
  kind: DataSourceKind;
  label?: string;
  className?: string;
}) {
  const presentation = sourcePresentation[kind];
  return (
    <Badge variant="outline" className={cn("gap-1.5 whitespace-nowrap font-medium", presentation.className, className)}>
      {kind === "live" ? <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" /> : null}
      {label ?? presentation.label}
    </Badge>
  );
}
