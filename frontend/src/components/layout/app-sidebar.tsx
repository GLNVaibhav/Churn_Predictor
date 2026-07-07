"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  UploadCloud,
  Workflow,
  Sparkles,
  FileSearch,
  BrainCircuit,
  FileBarChart2,
  Settings,
  Activity,
} from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/upload", label: "Upload Dataset", icon: UploadCloud },
  { href: "/pipeline", label: "Analysis Pipeline", icon: Workflow, flagship: true },
  { href: "/predictions", label: "Predictions", icon: Sparkles },
  { href: "/explanation", label: "Prediction Explanation", icon: FileSearch },
  { href: "/decision-intelligence", label: "Decision Intelligence", icon: BrainCircuit },
  { href: "/reports", label: "Reports", icon: FileBarChart2 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-border/60 bg-sidebar md:flex">
      <div className="flex h-14 items-center gap-2 border-b border-border/60 px-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Activity className="h-4 w-4" />
        </div>
        <div className="leading-none">
          <p className="text-sm font-semibold">Universal Churn</p>
          <p className="text-[11px] text-muted-foreground">Intelligence Platform</p>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-3">
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1 truncate">{item.label}</span>
              {item.flagship ? (
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              ) : null}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border/60 p-4">
        <div className="rounded-lg border border-border/60 bg-muted/30 p-3">
          <p className="text-xs font-medium">Mock Data Mode</p>
          <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
            Phase 1 UI — not yet connected to the Python backend.
          </p>
        </div>
      </div>
    </aside>
  );
}
