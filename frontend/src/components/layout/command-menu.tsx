"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NAV_ITEMS, WORKSPACE_SECTIONS } from "@/lib/navigation";
import { useExecutionContext } from "@/lib/context/execution-context";
import { cn } from "@/lib/utils";
import { FileSpreadsheet, Search } from "lucide-react";

type CommandAction = {
  id: string;
  label: string;
  description: string;
  href: string;
  keywords: string;
};

export function CommandMenu() {
  const router = useRouter();
  const ctx = useExecutionContext();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const actions = useMemo<CommandAction[]>(() => {
    const navActions = NAV_ITEMS.map((item) => ({
      id: item.href,
      label: item.label,
      description: item.description,
      href: item.href,
      keywords: `${item.label} ${item.description}`,
    }));
    const workspaceActions = WORKSPACE_SECTIONS.map((section) => ({
      id: `workspace-${section.id}`,
      label: `Open ${section.label}`,
      description: ctx.executionId ? "Open this section for the selected execution" : "Select an execution from history to use this section",
      href: ctx.executionId
        ? `/workspace?execution_id=${encodeURIComponent(ctx.executionId)}&tab=${section.id}`
        : `/workspace?tab=${section.id}`,
      keywords: `workspace ${section.label} analysis prediction evidence reports decision comparison`,
    }));
    return [
      { id: "upload-csv", label: "Upload CSV", description: "Start a new churn run from a customer dataset", href: "/upload", keywords: "new run upload csv dataset analysis" },
      { id: "landing", label: "Open product page", description: "View UCIF landing page", href: "/", keywords: "home landing product ucif" },
      ...navActions,
      ...workspaceActions,
    ];
  }, [ctx.executionId]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return actions.slice(0, 8);
    return actions
      .filter((action) => action.keywords.toLowerCase().includes(normalized))
      .slice(0, 8);
  }, [actions, query]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
    }
    function onOpenCommand() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("ucif:open-command-menu", onOpenCommand);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("ucif:open-command-menu", onOpenCommand);
    };
  }, []);

  function run(action: CommandAction) {
    setOpen(false);
    setQuery("");
    router.push(action.href);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="top-[18%] max-w-xl translate-y-0 p-0" showCloseButton={false}>
        <DialogHeader className="sr-only">
          <DialogTitle>Command Menu</DialogTitle>
          <DialogDescription>Search and navigate UCIF workspace actions.</DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-2 border-b border-border px-3 py-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Upload CSV, open analysis workspace, find reports…"
            className="h-10 border-0 px-0 text-sm focus-visible:ring-0"
          />
          <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">Esc</kbd>
        </div>
        <div className="max-h-[380px] overflow-y-auto p-2">
          {filtered.length ? (
            filtered.map((action, index) => (
              <button
                key={action.id}
                type="button"
                onClick={() => run(action)}
                className={cn(
                  "flex w-full flex-col rounded-md px-3 py-2 text-left transition-colors hover:bg-muted",
                  index === 0 && "bg-muted/55",
                )}
              >
                <span className="flex items-center gap-2 text-sm font-medium">
                  {action.id === "upload-csv" ? <FileSpreadsheet className="h-3.5 w-3.5 text-muted-foreground" /> : null}
                  {action.label}
                </span>
                <span className="mt-0.5 text-xs text-muted-foreground">{action.description}</span>
              </button>
            ))
          ) : (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">No matching command.</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
