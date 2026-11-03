"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { ApiError } from "@/lib/api/client";
import { getExecution, isExecutionActive } from "@/lib/api/executions";
import { useExecutionContext } from "@/lib/context/execution-context";
import { canonicalPayload } from "@/lib/api/view-models";
import { markInvalidExecution } from "@/lib/hooks/use-latest-run-selection";

function isMissingExecution(error: unknown) {
  if (error instanceof ApiError && error.status === 404) return true;
  return error instanceof Error && /execution not found/i.test(error.message);
}

/** Loads one selected execution and keeps its valid identity in local context. */
export function useAnalysisWorkspace(executionId?: string | null) {
  const ctx = useExecutionContext();
  const id = executionId || ctx.executionId;

  const query = useQuery({
    queryKey: ["workspace", id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => getExecution(id as string, signal),
    retry: (failureCount, error) => !isMissingExecution(error) && failureCount < 2,
    retryDelay: (attempt) => Math.min(500 * 2 ** attempt, 2000),
    staleTime: 30_000,
    refetchInterval: (q) => {
      const payload = canonicalPayload(q.state.data);
      const execution = payload?.execution as Record<string, unknown> | undefined;
      const status = String(execution?.status || payload?.status || "");
      return isExecutionActive(status) ? 2000 : false;
    },
  });

  useEffect(() => {
    if (isMissingExecution(query.error)) {
      if (id) markInvalidExecution(id);
      if (ctx.executionId === id) ctx.clearExecutionContext();
      return;
    }
    const payload = canonicalPayload(query.data);
    if (!payload || !id) return;
    const execution = payload.execution as Record<string, unknown> | undefined;
    const dataset = payload.dataset as Record<string, unknown> | undefined;
    const sameContext = ctx.executionId === id;
    const next = {
      executionId: id,
      uploadId: typeof payload.upload_id === "string" ? payload.upload_id : sameContext ? ctx.uploadId : null,
      filename: typeof dataset?.filename === "string" ? dataset.filename : sameContext ? ctx.filename : null,
      sector:
        typeof dataset?.sector === "string"
          ? dataset.sector
          : typeof payload.sector === "string"
            ? payload.sector
            : sameContext ? ctx.sector : null,
      status:
        typeof execution?.status === "string"
          ? execution.status
          : typeof payload.status === "string"
            ? payload.status
            : sameContext ? ctx.status : null,
    };
    if (
      ctx.executionId !== next.executionId || ctx.uploadId !== next.uploadId || ctx.filename !== next.filename ||
      ctx.sector !== next.sector || ctx.status !== next.status
    ) ctx.setExecutionContext(next);
  }, [query.data, query.error, id, ctx]);

  return {
    ...query,
    executionId: id,
    payload: canonicalPayload(query.data),
    reports: Array.isArray(canonicalPayload(query.data)?.reports)
      ? canonicalPayload(query.data)?.reports as Record<string, unknown>[]
      : [],
  };
}
