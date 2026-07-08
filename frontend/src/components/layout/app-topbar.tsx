"use client";

import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useDevMode } from "@/lib/context/dev-mode-context";
import { resolvePageMeta } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { Code2, Briefcase } from "lucide-react";

export function AppTopbar() {
  const pathname = usePathname();
  const meta = resolvePageMeta(pathname);
  const { developerMode, toggleDeveloperMode } = useDevMode();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border/40 bg-[#0d1321]/80 px-5 backdrop-blur-md">
      <div>
        <h1 className="text-sm font-semibold leading-none text-white">{meta.label}</h1>
        {meta.description ? (
          <p className="mt-1 max-w-xl truncate text-xs text-slate-400">{meta.description}</p>
        ) : null}
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center rounded-full border border-border/40 bg-black/20 p-0.5 text-xs font-medium">
          <button
            type="button"
            onClick={() => developerMode && toggleDeveloperMode()}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors",
              !developerMode ? "bg-white/10 text-white shadow-sm" : "text-slate-400 hover:text-white"
            )}
          >
            <Briefcase className="h-3.5 w-3.5" />
            Business
          </button>
          <button
            type="button"
            onClick={() => !developerMode && toggleDeveloperMode()}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors",
              developerMode ? "bg-white/10 text-white shadow-sm" : "text-slate-400 hover:text-white"
            )}
          >
            <Code2 className="h-3.5 w-3.5" />
            Developer
          </button>
        </div>
        <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
          Live API
        </Badge>
        <Avatar className="h-8 w-8 border border-border/40">
          <AvatarFallback className="bg-blue-500/20 text-xs text-blue-300">UC</AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
}
