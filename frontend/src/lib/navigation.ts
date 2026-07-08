import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  PlusCircle,
  History,
  FileBarChart2,
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
  primary?: boolean;
};

/** Single source of truth for sidebar + topbar navigation. */
export const NAV_ITEMS: NavItem[] = [
  {
    href: "/dashboard",
    label: "Home",
    description: "Mission Control — framework health, recent analyses, quick actions",
    icon: LayoutDashboard,
  },
  {
    href: "/upload",
    label: "New Analysis",
    description: "Upload a dataset and run the intelligence pipeline",
    icon: PlusCircle,
    primary: true,
  },
  {
    href: "/workspace",
    label: "Analysis Workspace",
    description: "Unified view of coverage, quality, routing, prediction, and decision",
    icon: Microscope,
  },
  {
    href: "/analyses",
    label: "Analyses",
    description: "Execution history and status",
    icon: History,
  },
  {
    href: "/reports",
    label: "Reports",
    description: "Executive, technical, and audit reports",
    icon: FileBarChart2,
  },
  {
    href: "/knowledge",
    label: "Knowledge",
    description: "Business rules, sectors, and framework documentation",
    icon: BookOpen,
  },
  {
    href: "/monitoring",
    label: "Monitoring",
    description: "Framework health, execution trends, and version tracking",
    icon: Activity,
  },
  {
    href: "/settings",
    label: "Settings",
    description: "API configuration, environment, and framework information",
    icon: Settings,
  },
];

export const NAV_BY_HREF = Object.fromEntries(NAV_ITEMS.map((item) => [item.href, item]));

export type WorkspaceSection =
  | "overview"
  | "pipeline"
  | "coverage"
  | "quality"
  | "routing"
  | "prediction"
  | "reasoning"
  | "decision"
  | "reports";

export const WORKSPACE_SECTIONS: { id: WorkspaceSection; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "pipeline", label: "Pipeline" },
  { id: "coverage", label: "Coverage" },
  { id: "quality", label: "Quality" },
  { id: "routing", label: "Routing" },
  { id: "prediction", label: "Prediction" },
  { id: "reasoning", label: "Reasoning" },
  { id: "decision", label: "Decision" },
  { id: "reports", label: "Reports" },
];

/** Legacy routes → workspace tab redirects */
export const LEGACY_ROUTE_REDIRECTS: Record<string, string> = {
  "/pipeline": "/workspace?tab=pipeline",
  "/predictions": "/workspace?tab=prediction",
  "/explanation": "/workspace?tab=reasoning",
  "/decision-intelligence": "/workspace?tab=decision",
};

export function resolvePageMeta(pathname: string): NavItem {
  const base = pathname.split("?")[0];
  if (NAV_BY_HREF[base]) return NAV_BY_HREF[base];
  if (base.startsWith("/workspace")) return NAV_BY_HREF["/workspace"];
  return { href: base, label: "Universal Churn", description: "", icon: LayoutDashboard };
}
