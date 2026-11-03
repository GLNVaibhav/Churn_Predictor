"use client";

import { UcifLogo } from "@/components/brand/ucif-logo";
import { AppNavigation } from "@/components/layout/app-navigation";

export function AppSidebar() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex print:hidden" aria-label="Application sidebar">
      <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-4">
        <UcifLogo tone="sidebar" sublabel="Retention Intelligence" />
      </div>
      <div className="flex-1 overflow-y-auto p-3"><AppNavigation /></div>
      <div className="border-t border-sidebar-border px-4 py-3 text-[11px] text-sidebar-foreground/55">Universal Churn Intelligence</div>
    </aside>
  );
}
