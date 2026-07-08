"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { WorkspaceSectionView } from "@/components/workspace/workspace-sections";
import { Button } from "@/components/ui/button";
import { useAnalysisWorkspace } from "@/lib/hooks/use-analysis-workspace";
import { WORKSPACE_SECTIONS, type WorkspaceSection } from "@/lib/navigation";
import { useExecutionContext } from "@/lib/context/execution-context";
import { cn } from "@/lib/utils";
import { PlusCircle } from "lucide-react";

export default function WorkspacePageInner() {
  const searchParams = useSearchParams();
  const tab = (searchParams.get("tab") as WorkspaceSection) || "overview";
  const ctx = useExecutionContext();
  const workspace = useAnalysisWorkspace();

  return (
    <PageShell>
      {workspace.error ? (
        <ErrorBanner error={workspace.error} onRetry={() => workspace.refetch()} />
      ) : null}

      {!ctx.executionId ? (
        <EmptyState
          title="No analysis selected"
          description="Start a new analysis or open one from history."
          action={
            <Link href="/upload">
              <Button size="sm"><PlusCircle className="mr-2 h-4 w-4" />New Analysis</Button>
            </Link>
          }
        />
      ) : workspace.isLoading ? (
        <LoadingState label="Loading analysis workspace..." />
      ) : null}

      {ctx.executionId && workspace.payload ? (
        <>
          <div className="flex flex-wrap gap-1 rounded-lg border border-border/40 bg-black/20 p-1">
            {WORKSPACE_SECTIONS.map((section) => (
              <Link
                key={section.id}
                href={`/workspace?tab=${section.id}`}
                className={cn(
                  "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  tab === section.id
                    ? "bg-blue-500/20 text-blue-300"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                )}
              >
                {section.label}
              </Link>
            ))}
          </div>
          <WorkspaceSectionView section={tab} data={workspace} />
        </>
      ) : null}
    </PageShell>
  );
}
