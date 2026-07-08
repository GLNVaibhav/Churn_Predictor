"use client";

import { NAV_ITEMS } from "@/lib/navigation";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Activity } from "lucide-react";

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border/60 bg-[#0a0f1a] md:flex">
      <div className="flex h-14 items-center gap-2.5 border-b border-border/40 px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 text-white shadow-lg shadow-blue-500/20">
          <Activity className="h-4 w-4" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-tight text-white">UCIF</p>
          <p className="text-[10px] text-slate-400">Decision Intelligence</p>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2.5">
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
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-all",
                isActive
                  ? "bg-blue-500/15 text-blue-300 shadow-inner"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              )}
            >
              <Icon className="h-4 w-4 shrink-0 opacity-80" />
              <span className="flex-1 truncate">{item.label}</span>
              {item.primary ? (
                <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-blue-300">
                  Start
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border/40 p-3">
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2.5">
          <p className="text-[11px] font-medium text-emerald-400">Framework Online</p>
          <p className="mt-0.5 text-[10px] text-slate-500">Connected to FastAPI backend</p>
        </div>
      </div>
    </aside>
  );
}
