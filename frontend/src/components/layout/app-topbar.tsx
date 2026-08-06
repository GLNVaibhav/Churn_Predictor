"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { resolvePageMeta } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { apiRequest } from "@/lib/api/client";
import { useQuery } from "@tanstack/react-query";
import { Bell, Moon, Plus, Sun, Search } from "lucide-react";
import { useAuth } from "@/lib/context/auth-context";
import { useTheme } from "@/lib/context/theme-context";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function AppTopbar() {
  const pathname = usePathname();
  const [workspaceTab, setWorkspaceTab] = useState<string | null>(null);
  useEffect(() => {
    setWorkspaceTab(new URLSearchParams(window.location.search).get("tab"));
  }, [pathname]);
  const workspaceMeta = {
    overview: { label: "Workspace Overview", description: "Predictions, explanations, reports, comparison, and run evidence." },
    pipeline: { label: "Pipeline", description: "Step-by-step progress from intake to decision support." },
    coverage: { label: "Coverage", description: "Schema coverage, semantic matches, and missing critical fields." },
    semantic: { label: "Semantic", description: "Business meanings, feature trace, and semantic validation." },
    quality: { label: "Quality", description: "Validation checks, leakage detection, and quality gates." },
    routing: { label: "Routing", description: "Model routing decisions and selection rationale." },
    prediction: { label: "Prediction", description: "Customer-level churn scoring and cohort output." },
    reasoning: { label: "Reasoning", description: "Business explanation and recommendation narrative." },
    decision: { label: "Decision", description: "Decision intelligence, readiness, and ABIL context." },
    cli: { label: "Run Evidence", description: "Run metadata, status, and comparison evidence." },
    reports: { label: "Reports", description: "Executive, technical, and audit report views." },
  } as const;
  const meta = pathname.startsWith("/workspace") && workspaceTab && workspaceTab in workspaceMeta
    ? workspaceMeta[workspaceTab as keyof typeof workspaceMeta]
    : resolvePageMeta(pathname);
  const health = useQuery({
    queryKey: ["api-health"],
    queryFn: ({ signal }) => apiRequest<{ status: string }>("/api/v1/health", {}, signal),
    refetchInterval: 15000,
    retry: 1,
  });
  const online = health.data?.status === "OK";
  const auth = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border/70 bg-card/90 px-5 backdrop-blur">
      <div>
        <h1 className="text-sm font-semibold leading-none tracking-tight text-foreground">{meta.label}</h1>
        {meta.description ? (
          <p className="mt-1 max-w-xl truncate text-xs text-muted-foreground">{meta.description}</p>
        ) : null}
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event("ucif:open-command-menu"))}
          className="hidden h-8 items-center gap-2 rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground hover:bg-muted lg:flex"
        >
          <Plus className="h-3.5 w-3.5 text-primary" />
          New
          <kbd className="rounded border border-border bg-muted px-1 py-0.5 text-[10px] text-muted-foreground">Ctrl K</kbd>
        </button>
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event("ucif:open-command-menu"))}
          className="hidden h-8 items-center gap-2 rounded-md border border-border bg-background px-3 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground lg:flex"
        >
          <Search className="h-3.5 w-3.5" />
          Search
          <kbd className="ml-1 rounded border border-border bg-muted px-1 py-0.5 text-[10px]">Ctrl K</kbd>
        </button>
        <Tooltip>
          <TooltipTrigger>
            <span
              className="hidden h-8 w-8 items-center justify-center rounded-md border border-border bg-background text-muted-foreground sm:flex"
              aria-label={online ? "Analysis service online" : "Analysis service unavailable"}
            >
              <span className={cn("h-2.5 w-2.5 rounded-full", online ? "animate-pulse bg-emerald-500" : "bg-amber-500")} />
            </span>
          </TooltipTrigger>
          <TooltipContent>{online ? "Analysis service online" : "Analysis service unavailable"}</TooltipContent>
        </Tooltip>
        <button
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-muted-foreground hover:text-foreground"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        <Link href="/monitoring" className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-muted-foreground hover:text-foreground">
          <Bell className="h-4 w-4" />
        </Link>
        {auth.user ? (
          <button type="button" onClick={() => auth.logout()} className="flex items-center gap-2 rounded-md border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted">
            <Avatar className="h-7 w-7 border border-border">
              <AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">
                {auth.user.name.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <span className="hidden max-w-28 truncate sm:inline">{auth.user.name}</span>
          </button>
        ) : (
          <Link href="/signin" className="flex items-center gap-2 rounded-md border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted">
            <Avatar className="h-7 w-7 border border-border">
              <AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">UC</AvatarFallback>
            </Avatar>
            <span className="hidden sm:inline">Sign in</span>
          </Link>
        )}
      </div>
    </header>
  );
}
