"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  getExecution,
  getExecutionContext,
  getExecutionDecision,
  getExecutionEvents,
  getExecutionPipeline,
  getExecutionPredictions,
  isExecutionActive,
  listExecutions,
} from "@/lib/api/executions";
import { getExecutionReports } from "@/lib/api/reports";
import { startAnalysis } from "@/lib/api/analysis";
import { uploadDataset } from "@/lib/api/upload";
import { useExecutionContext } from "@/lib/context/execution-context";

export function useExecution(executionId?: string | null) {
  const ctx = useExecutionContext();
  const id = executionId || ctx.executionId;
  const query = useQuery({
    queryKey: ["execution", id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => getExecution(id as string, signal),
    refetchInterval: (query) => {
      const status = String(query.state.data?.execution?.status || "");
      return isExecutionActive(status) ? 2000 : false;
    },
  });

  useEffect(() => {
    const execution = query.data?.execution;
    if (!execution || !id) return;
    const inner = execution.execution as Record<string, unknown> | undefined;
    ctx.setExecutionContext({
      executionId: id,
      uploadId: String(execution.upload_id || ctx.uploadId || ""),
      filename: String((execution.dataset as Record<string, unknown> | undefined)?.filename || execution.filename || ctx.filename || ""),
      sector: String((execution.dataset as Record<string, unknown> | undefined)?.sector || execution.sector || ctx.sector || ""),
      status: String(inner?.status || execution.status || ctx.status || ""),
    });
  }, [query.data, id]);

  return query;
}

export function useExecutionPipeline(executionId?: string | null, status?: string | null) {
  const ctx = useExecutionContext();
  const id = executionId || ctx.executionId;
  return useQuery({
    queryKey: ["pipeline", id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => getExecutionPipeline(id as string, signal),
    refetchInterval: () => (isExecutionActive(status) ? 2000 : false),
  });
}

export function useExecutionPredictions(executionId?: string | null) {
  const ctx = useExecutionContext();
  const id = executionId || ctx.executionId;
  return useQuery({
    queryKey: ["predictions", id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => getExecutionPredictions(id as string, signal),
  });
}

export function useExecutionReports(executionId?: string | null) {
  const ctx = useExecutionContext();
  const id = executionId || ctx.executionId;
  return useQuery({
    queryKey: ["reports", id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => getExecutionReports(id as string, signal),
  });
}

export function useExecutionDecision(executionId?: string | null) {
  const ctx = useExecutionContext();
  const id = executionId || ctx.executionId;
  return useQuery({
    queryKey: ["decision", id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => getExecutionDecision(id as string, signal),
  });
}

export function useExecutionEvents(executionId?: string | null, status?: string | null) {
  const ctx = useExecutionContext();
  const id = executionId || ctx.executionId;
  return useQuery({
    queryKey: ["events", id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => getExecutionEvents(id as string, signal),
    refetchInterval: () => (isExecutionActive(status) ? 2000 : false),
  });
}

export function useExecutionHistory() {
  return useQuery({
    queryKey: ["executions"],
    queryFn: ({ signal }) => listExecutions(signal),
  });
}

export function useExecutionContextQuery(executionId?: string | null) {
  const ctx = useExecutionContext();
  const id = executionId || ctx.executionId;
  return useQuery({
    queryKey: ["context", id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => getExecutionContext(id as string, signal),
  });
}

export function useUploadDataset() {
  const ctx = useExecutionContext();
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress?: (progress: number) => void }) =>
      uploadDataset(file, onProgress),
    onSuccess: (upload) => {
      ctx.setExecutionContext({
        uploadId: upload.upload_id,
        executionId: null,
        filename: upload.filename,
        sector: upload.sector,
        status: upload.status,
      });
    },
  });
}

export function useStartExecution() {
  const ctx = useExecutionContext();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => startAnalysis(ctx.uploadId as string, ctx.sector),
    onSuccess: (analysis) => {
      ctx.setExecutionContext({
        uploadId: analysis.upload_id,
        executionId: analysis.execution_id,
        status: analysis.status,
      });
      queryClient.invalidateQueries({ queryKey: ["executions"] });
      queryClient.invalidateQueries({ queryKey: ["execution", analysis.execution_id] });
    },
  });
}
