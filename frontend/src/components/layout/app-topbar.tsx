"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { resolvePageMeta } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { apiRequest } from "@/lib/api/client";
import { useQuery } from "@tanstack/react-query";
import { Activity, Moon, Plus, Sun, Search, Menu } from "lucide-react";
import { useAuth } from "@/lib/context/auth-context";
import { useTheme } from "@/lib/context/theme-context";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { AppNavigation } from "@/components/layout/app-navigation";
import { UcifLogo } from "@/components/brand/ucif-logo";
import { DataSourceBadge } from "@/components/shared/data-source-badge";
import { useState } from "react";

export function AppTopbar() {
  const pathname = usePathname();
  const meta = resolvePageMeta(pathname);
  const health = useQuery({
    queryKey: ["api-health"],
    queryFn: ({ signal }) => apiRequest<{ status: string }>("/api/v1/health", {}, signal),
    refetchInterval: 15000,
    retry: 1,
  });
  const online = health.data?.status === "OK" && !health.isError;
  const healthKind = online ? "live" : health.isPending ? "loading" : health.isError ? "failed" : "unavailable";
  const auth = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [navigationOpen, setNavigationOpen] = useState(false);

  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-border/70 bg-card/95 px-3 backdrop-blur print:hidden sm:px-5">
      <div className="flex min-w-0 items-center gap-3">
        <Sheet open={navigationOpen} onOpenChange={setNavigationOpen}>
          <SheetTrigger
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-background text-foreground outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring md:hidden"
            aria-label="Open main navigation"
          >
            <Menu aria-hidden="true" className="h-4 w-4" />
          </SheetTrigger>
          <SheetContent side="left" className="border-sidebar-border bg-sidebar p-0 text-sidebar-foreground sm:max-w-xs">
            <SheetHeader className="border-b border-sidebar-border px-4 py-4">
              <SheetTitle className="text-sidebar-foreground"><UcifLogo tone="sidebar" sublabel="Retention Intelligence" /></SheetTitle>
              <SheetDescription className="sr-only">Navigate between UCIF application areas.</SheetDescription>
            </SheetHeader>
            <div className="overflow-y-auto p-3"><AppNavigation onNavigate={() => setNavigationOpen(false)} /></div>
          </SheetContent>
        </Sheet>
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold leading-none tracking-tight text-foreground">{meta.label}</h1>
          {meta.description ? (
            <p className="mt-1 max-w-xl truncate text-xs text-muted-foreground">{meta.description}</p>
          ) : null}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event("ucif:open-command-menu"))}
          className="hidden h-8 items-center gap-2 rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:flex"
        >
          <Plus className="h-3.5 w-3.5 text-primary" />
          New
          <kbd className="rounded border border-border bg-muted px-1 py-0.5 text-[10px] text-muted-foreground">Ctrl K</kbd>
        </button>
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event("ucif:open-command-menu"))}
          className="hidden h-8 items-center gap-2 rounded-md border border-border bg-background px-3 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:flex"
        >
          <Search className="h-3.5 w-3.5" />
          Search
          <kbd className="ml-1 rounded border border-border bg-muted px-1 py-0.5 text-[10px]">Ctrl K</kbd>
        </button>
        <div className="hidden sm:block" aria-live="polite" aria-atomic="true">
          <DataSourceBadge kind={healthKind} label={online ? "API online" : health.isPending ? "Checking API" : health.isError ? "API request failed" : "API unavailable"} />
        </div>
        <span
          role="status"
          aria-live="polite"
          aria-label={online ? "Analysis service online" : health.isPending ? "Checking analysis service connection" : health.isError ? "Analysis service health request failed" : "Analysis service unavailable"}
          title={online ? "Analysis service online" : health.isPending ? "Checking analysis service" : health.isError ? "Analysis service health request failed" : "Analysis service unavailable"}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-background sm:hidden"
        >
          <span className={cn("h-2.5 w-2.5 rounded-full", online ? "bg-success" : health.isPending ? "bg-info" : "bg-muted-foreground")} />
        </span>
        <button
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        <Link href="/monitoring" aria-label="Open monitoring" className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Activity className="h-4 w-4" />
        </Link>
        {auth.user ? (
          <button type="button" onClick={() => auth.logout()} className="flex items-center gap-2 rounded-md border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <Avatar className="h-7 w-7 border border-border">
              <AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">
                {auth.user.name.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <span className="hidden max-w-28 truncate sm:inline">{auth.user.name}</span>
          </button>
        ) : (
          <Link href="/signin" className="flex items-center gap-2 rounded-md border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
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
