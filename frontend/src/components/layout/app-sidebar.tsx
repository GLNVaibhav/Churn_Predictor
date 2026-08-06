"use client";

import { NAV_ITEMS } from "@/lib/navigation";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import { UcifLogo } from "@/components/brand/ucif-logo";

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
      <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-4">
        <UcifLogo tone="sidebar" sublabel="Retention Intelligence" />
      </div>
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-2.5 rounded-md px-3 py-2.5 text-[13px] font-medium transition-colors",
                isActive
                  ? "bg-sidebar-foreground text-sidebar shadow-sm"
                  : "text-sidebar-foreground/66 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )}
            >
              <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-sidebar-primary" : "opacity-75")} />
              <span className="flex-1 truncate">{item.label}</span>
              <ChevronRight className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-50" />
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
