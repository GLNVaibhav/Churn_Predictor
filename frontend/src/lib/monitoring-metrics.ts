type ExecutionMetricInput = {
  status?: string | null;
  execution_time_ms?: number | null;
};

export type ServiceHealthState = "HEALTHY" | "DEGRADED" | "UNAVAILABLE" | "UNKNOWN";

export function serviceHealthState(
  status: string | null | undefined,
  isPending: boolean,
  isError: boolean,
): ServiceHealthState {
  if (isError) return "UNAVAILABLE";
  if (isPending || !status) return "UNKNOWN";
  return ["OK", "HEALTHY"].includes(status.trim().toUpperCase()) ? "HEALTHY" : "DEGRADED";
}

export function executionMetrics(runs: ExecutionMetricInput[]) {
  const succeeded = runs.filter((run) => ["SUCCEEDED", "SUCCESS"].includes(String(run.status || "").toUpperCase())).length;
  const failed = runs.filter((run) => String(run.status || "").toUpperCase() === "FAILED").length;
  const runtimes = runs
    .map((run) => run.execution_time_ms == null ? Number.NaN : Number(run.execution_time_ms))
    .filter((runtime) => Number.isFinite(runtime) && runtime >= 0);

  return {
    total: runs.length,
    succeeded,
    failed,
    averageRuntimeMs: runtimes.length ? runtimes.reduce((total, value) => total + value, 0) / runtimes.length : null,
    successRatePercent: runs.length ? Math.round((succeeded / runs.length) * 100) : null,
  };
}
