"use client";

import { useEffect } from "react";
import { useExecutionContext } from "@/lib/context/execution-context";
import { useExecutionHistory } from "@/lib/hooks/use-execution";
import { isExpiredExecution } from "@/lib/execution-expiry";

type LatestRunOptions = {
  disabled?: boolean;
  preferLatest?: boolean;
};

const INVALID_EXECUTIONS_KEY = "ucif:invalid-executions";

function invalidExecutions() {
  if (typeof window === "undefined") return new Set<string>();
  try {
    const value = JSON.parse(window.localStorage.getItem(INVALID_EXECUTIONS_KEY) || "[]");
    return new Set(Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []);
  } catch {
    return new Set<string>();
  }
}

export function markInvalidExecution(executionId: string) {
  if (typeof window === "undefined") return;
  const invalid = invalidExecutions();
  invalid.add(executionId);
  window.localStorage.setItem(INVALID_EXECUTIONS_KEY, JSON.stringify([...invalid].slice(-50)));
}

export function useLatestRunSelection(options: LatestRunOptions = {}) {
  const ctx = useExecutionContext();
  const history = useExecutionHistory();

  useEffect(() => {
    if (options.disabled || !history.data?.length) return;
    const invalid = invalidExecutions();
    if (ctx.executionId && (isExpiredExecution(ctx.executionId) || invalid.has(ctx.executionId))) {
      ctx.clearExecutionContext();
      return;
    }
    const latest = history.data.find(
      (run) => run.execution_id && !isExpiredExecution(run.execution_id) && !invalid.has(run.execution_id),
    );
    if (!latest?.execution_id) return;
    if (!options.preferLatest && ctx.executionId) return;
    if (ctx.executionId === latest.execution_id) return;
    ctx.setExecutionContext({
      executionId: latest.execution_id,
      filename: latest.filename || ctx.filename,
      sector: latest.sector || ctx.sector,
      status: latest.status || ctx.status,
    });
  }, [ctx, history.data, options.disabled, options.preferLatest]);

  return history;
}
