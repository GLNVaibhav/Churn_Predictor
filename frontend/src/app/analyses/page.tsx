"use client";

import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { DataSourceBadge } from "@/components/shared/data-source-badge";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { sectorLabel } from "@/lib/constants/sectors";
import { ArrowRight, PlusCircle } from "lucide-react";

function dateText(value?: string | null) {
  if (!value) return "Not reported";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function fileName(value?: string | null) {
  if (!value) return "Not reported";
  const parts = value.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || value;
}

export default function AnalysesPage() {
  const history = useExecutionHistory();
  const runs = history.data || [];

  return (
    <PageShell>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><h1 className="text-xl font-semibold tracking-tight">Execution History</h1><p className="mt-1 text-sm text-muted-foreground">Open a persisted execution to inspect the API results and intelligence available for that run.</p></div>
        <Button render={<Link href="/upload" />}><PlusCircle className="mr-2 h-4 w-4" />New analysis</Button>
      </div>

      {history.error ? <ErrorBanner error={history.error} onRetry={() => history.refetch()} /> : null}
      {history.isLoading ? <LoadingState label="Loading execution history…" /> : null}
      {!history.isLoading && !history.error ? <SectionCard title="Analyses" description="Execution identifiers and metadata returned by the history API." action={runs.length ? <DataSourceBadge kind="historical" label={`${runs.length} API records`} /> : undefined}>
        {runs.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {runs.map((run, index) => {
            const id = run.execution_id;
            return (
              <article key={id || `run-${index}`} className="rounded-xl border border-border bg-background p-4 transition-colors hover:border-primary/40 hover:bg-muted/10">
                <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-semibold">{fileName(run.filename)}</p><p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">{id || "Execution ID not reported"}</p></div><Badge variant="outline">{run.status || "Status not reported"}</Badge></div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-xs"><div><dt className="text-muted-foreground">Sector</dt><dd className="mt-1 font-medium">{run.sector ? sectorLabel(run.sector) : "Not reported"}</dd></div><div><dt className="text-muted-foreground">Started</dt><dd className="mt-1 font-medium">{dateText(run.started_at || run.created_at)}</dd></div><div><dt className="text-muted-foreground">Runtime (ms)</dt><dd className="mt-1 font-medium tabular-nums">{run.execution_time_ms ?? "Not reported"}</dd></div><div><dt className="text-muted-foreground">Completed</dt><dd className="mt-1 font-medium">{dateText(run.completed_at)}</dd></div></dl>
                {id ? <Button className="mt-4" variant="outline" size="sm" render={<Link href={`/workspace?execution_id=${encodeURIComponent(id)}`} />}>Open workspace<ArrowRight className="ml-2 h-4 w-4" /></Button> : <p className="mt-4 text-xs text-muted-foreground">This history item has no execution identifier and cannot be opened.</p>}
              </article>
            );
          })}
        </div> : <EmptyState title="No executions returned" description="Start a new analysis to create an execution that can be opened in the workspace." action={<Button render={<Link href="/upload" />}>Start an analysis<ArrowRight className="ml-2 h-4 w-4" /></Button>} />}
      </SectionCard> : null}
    </PageShell>
  );
}
