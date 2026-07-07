"use client";

import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useDevMode } from "@/lib/context/dev-mode-context";
import { cn } from "@/lib/utils";
import { Code2, Briefcase } from "lucide-react";

const titleMap: Record<string, { title: string; description: string }> = {
  "/dashboard": { title: "Dashboard", description: "Cross-sector churn intelligence overview" },
  "/upload": { title: "Upload Dataset", description: "Ingest a new dataset for analysis" },
  "/pipeline": { title: "Analysis Pipeline", description: "End-to-end framework execution flow" },
  "/predictions": { title: "Predictions", description: "Scored records across all sectors" },
  "/explanation": { title: "Prediction Explanation", description: "Feature-level rationale per record" },
  "/decision-intelligence": { title: "Decision Intelligence", description: "Routing rationale and business concepts" },
  "/reports": { title: "Reports", description: "Generated execution and explanation reports" },
  "/settings": { title: "Settings", description: "Sector configuration and model registry" },
};

export function AppTopbar() {
  const pathname = usePathname();
  const meta = titleMap[pathname] ?? { title: "Universal Churn", description: "" };
  const { developerMode, toggleDeveloperMode } = useDevMode();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border/60 bg-background/80 px-6 backdrop-blur">
      <div>
        <h1 className="text-sm font-semibold leading-none">{meta.title}</h1>
        <p className="mt-1 text-xs text-muted-foreground">{meta.description}</p>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center rounded-full border border-border/60 bg-muted/40 p-0.5 text-xs font-medium">
          <button
            type="button"
            onClick={() => developerMode && toggleDeveloperMode()}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors",
              !developerMode ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
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
              developerMode ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Code2 className="h-3.5 w-3.5" />
            Developer
          </button>
        </div>
        <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
          Live API
        </Badge>
        <Avatar className="h-8 w-8">
          <AvatarFallback className="text-xs">RA</AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
}
