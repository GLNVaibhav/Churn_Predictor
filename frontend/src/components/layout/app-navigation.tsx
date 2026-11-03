"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";
import { NAV_ITEMS } from "@/lib/navigation";
import { cn } from "@/lib/utils";

const groups = [
  { id: "workspace", label: "WORKSPACE" },
  { id: "intelligence", label: "INTELLIGENCE" },
  { id: "system", label: "SYSTEM" },
] as const;

export function AppNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const reduceMotion = useReducedMotion();

  return (
    <nav aria-label="Main navigation" className="flex flex-col gap-5">
      {groups.map((group) => {
        const items = NAV_ITEMS.filter((item) => item.group === group.id);
        return (
          <div key={group.id}>
            <h2 className="mb-2 px-3 text-[10px] font-semibold tracking-[0.16em] text-sidebar-foreground/50">
              {group.label}
            </h2>
            <ul className="space-y-1">
              {items.map((item) => {
                const isActive = pathname === item.href ||
                  (item.href !== "/dashboard" && item.href !== "/upload" && pathname.startsWith(item.href));
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={isActive ? "page" : undefined}
                      className={cn(
                        "group relative flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-sidebar-ring",
                        isActive
                          ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
                          : "text-sidebar-foreground/72 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground",
                        item.href === "/upload" && "font-semibold text-sidebar-primary hover:text-sidebar-primary",
                      )}
                      title={item.description}
                    >
                      {isActive ? <motion.span layoutId={reduceMotion ? undefined : "app-navigation-indicator"} className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-sidebar-primary" transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 520, damping: 38 }} /> : null}
                      <Icon aria-hidden="true" className={cn("h-4 w-4 shrink-0", isActive ? "text-sidebar-primary" : "opacity-80")} />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}
