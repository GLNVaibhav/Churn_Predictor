import { cn } from "@/lib/utils";

type UcifLogoProps = {
  className?: string;
  markClassName?: string;
  showWordmark?: boolean;
  sublabel?: string;
  tone?: "default" | "sidebar" | "inverse";
};

export function UcifLogo({
  className,
  markClassName,
  showWordmark = true,
  sublabel = "Universal Churn Intelligence",
  tone = "default",
}: UcifLogoProps) {
  const textClass =
    tone === "sidebar"
      ? "text-sidebar-foreground"
      : tone === "inverse"
        ? "text-white"
        : "text-foreground";
  const mutedClass =
    tone === "sidebar"
      ? "text-sidebar-foreground/48"
      : tone === "inverse"
        ? "text-white/58"
        : "text-muted-foreground";

  return (
    <span className={cn("inline-flex items-center gap-3", className)}>
      <span
        className={cn(
          "relative flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-md bg-foreground text-background",
          tone === "sidebar" && "bg-sidebar-foreground text-sidebar",
          tone === "inverse" && "bg-neutral-50 text-neutral-950",
          markClassName,
        )}
        aria-hidden="true"
      >
        <svg viewBox="0 0 36 36" className="h-full w-full" role="img">
          <rect width="36" height="36" rx="8" fill="currentColor" opacity="0.08" />
          <path
            d="M8.2 20.3h4.1l2.5-7.7 5.1 14 2.8-9h5.1"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M18 7.4c3.4 0 6.5 1.7 8.3 4.6M18 28.6c-3.4 0-6.5-1.7-8.3-4.6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            opacity="0.62"
          />
        </svg>
      </span>
      {showWordmark ? (
        <span className="leading-tight">
          <span className={cn("block text-sm font-semibold tracking-tight", textClass)}>UCIF</span>
          <span className={cn("text-[11px] font-medium", mutedClass)}>{sublabel}</span>
        </span>
      ) : null}
    </span>
  );
}
