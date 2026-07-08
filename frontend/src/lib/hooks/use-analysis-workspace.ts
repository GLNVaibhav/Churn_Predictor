"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { getExecution, isExecutionActive } from "@/lib/api/executions";
import { useExecutionContext } from "@/lib/context/execution-context";
import { canonicalPayload } from "@/lib/api/view-models";

/**
 * Single-fetch hook for the Analysis Workspace.
 * Loads execution once and reuses cached data across all sections.
 */
export function useAnalysisWorkspace(executionId?: string | null) {
  const ctx = useExecutionContext();
  const id = executionId || ctx.executionId;

  const query = useQuery({
    queryKey: ["workspace", id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => getExecution(id as string, signal),
    staleTime: 30_000,
    refetchInterval: (q) => {
      const payload = canonicalPayload(q.state.data);
      const inner = payload?.execution as Record<string, unknown> | undefined;
      const status = String(inner?.status || payload?.status || "");
      return isExecutionActive(status) ? 2000 : false;
    },
  });

  useEffect(() => {
    const payload = canonicalPayload(query.data);
    if (!payload || !id) return;
    const inner = payload.execution as Record<string, unknown> | undefined;
    ctx.setExecutionContext({
      executionId: id,
      uploadId: String(payload.upload_id || ctx.uploadId || ""),
      filename: String((payload.dataset as Record<string, unknown> | undefined)?.filename || ctx.filename || ""),
      sector: String((payload.dataset as Record<string, unknown> | undefined)?.sector || ctx.sector || ""),
      status: String(inner?.status || payload.status || ctx.status || ""),
    });
  }, [query.data, id]);

  const payload = canonicalPayload(query.data);

  return {
    ...query,
    executionId: id,
    payload,
    predictions: (payload?.predictions as Record<string, unknown>[] | undefined) || [],
    coverage: (payload?.coverage as Record<string, unknown> | undefined) || null,
    quality: (payload?.quality as Record<string, unknown> | undefined) || null,
    routing: (payload?.routing as Record<string, unknown> | undefined) || null,
    prediction: (payload?.prediction as Record<string, unknown> | undefined) || null,
    reasoning: (payload?.prediction_explanation as Record<string, unknown> | undefined) || null,
    decision: (payload?.decision as Record<string, unknown> | undefined) || null,
    pipeline: (payload?.pipeline as Record<string, unknown> | undefined) || null,
    metadata: (payload?.metadata as Record<string, unknown> | undefined) || null,
    reports: (payload?.reports as Record<string, unknown>[] | undefined) || [],
    reportTexts: (payload?.report_texts as Record<string, string> | undefined) || {},
    featureEngineering: (payload?.feature_engineering as Record<string, unknown> | undefined) || null,
    diagnostics: (payload?.diagnostics as Record<string, unknown> | undefined) || null,
    executionState: (payload?.execution_state as Record<string, unknown> | undefined) || null,
  };
}
