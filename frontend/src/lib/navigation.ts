import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  PlusCircle,
  History,
  FileBarChart2,
  ListChecks,
  BookOpen,
  Activity,
  Settings,
  Microscope,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
  group?: "workspace" | "intelligence" | "system";
};

/** Single source of truth for sidebar + topbar navigation. */
export const NAV_ITEMS: NavItem[] = [
  {
    href: "/dashboard",
    group: "workspace",
    label: "Home",
    description: "Customer retention overview, recent analyses, and risk signals",
    icon: LayoutDashboard,
  },
  {
    href: "/upload",
    group: "workspace",
    label: "New Analysis",
    description: "Upload a dataset and create a churn analysis",
    icon: PlusCircle,
  },
  {
    href: "/workspace",
    group: "workspace",
    label: "Analysis Workspace",
    description: "Explore risk, explanations, decisions, and reports",
    icon: Microscope,
  },
  {
    href: "/analyses",
    group: "workspace",
    label: "Analyses",
    description: "Execution history and status",
    icon: History,
  },
  {
    href: "/reports",
    group: "intelligence",
    label: "Reports",
    description: "Executive, technical, and audit reports",
    icon: FileBarChart2,
  },
  {
    href: "/decision-intelligence",
    group: "intelligence",
    label: "Decision Intelligence",
    description: "Review execution recommendations and supporting business evidence",
    icon: ListChecks,
  },
  {
    href: "/knowledge",
    group: "intelligence",
    label: "Knowledge",
    description: "Business rules, sectors, and framework documentation",
    icon: BookOpen,
  },
  {
    href: "/monitoring",
    group: "system",
    label: "Monitoring",
    description: "Analysis health, activity, and run reliability",
    icon: Activity,
  },
  {
    href: "/settings",
    group: "system",
    label: "Settings",
    description: "Workspace preferences and account controls",
    icon: Settings,
  },
];

export const NAV_BY_HREF = Object.fromEntries(NAV_ITEMS.map((item) => [item.href, item]));

export type WorkspaceSection =
  | "overview"
  | "dataset"
  | "coverage"
  | "pipeline"
  | "predictions"
  | "diagnostics"
  | "business"
  | "decisions"
  | "reports";

export const WORKSPACE_SECTIONS: { id: WorkspaceSection; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "dataset", label: "Dataset Intelligence" },
  { id: "coverage", label: "Coverage Intelligence" },
  { id: "pipeline", label: "Pipeline" },
  { id: "predictions", label: "Predictions" },
  { id: "diagnostics", label: "Diagnostic Intelligence" },
  { id: "business", label: "Business Intelligence" },
  { id: "decisions", label: "Decision Intelligence" },
  { id: "reports", label: "Reports" },
];

/** Legacy routes to workspace tab redirects */
export const LEGACY_ROUTE_REDIRECTS: Record<string, string> = {
  "/pipeline": "/workspace?tab=pipeline",
  "/predictions": "/workspace?tab=predictions",
  "/explanation": "/workspace?tab=diagnostics",
  "/decision-intelligence": "/workspace?tab=decisions",
};

export function resolvePageMeta(pathname: string): NavItem {
  const base = pathname.split("?")[0];
  if (base === "/upload") {
    return {
      href: "/upload",
      label: "New Run",
      description: "Upload a dataset and create a churn analysis",
      icon: PlusCircle,
    };
  }
  if (NAV_BY_HREF[base]) return NAV_BY_HREF[base];
  if (base.startsWith("/workspace")) return NAV_BY_HREF["/workspace"];
  return { href: base, label: "Universal Churn", description: "", icon: LayoutDashboard };
}
