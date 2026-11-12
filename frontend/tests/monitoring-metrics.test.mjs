import assert from "node:assert/strict";
import { test } from "node:test";
import { executionMetrics, serviceHealthState } from "../src/lib/monitoring-metrics.ts";

test("monitoring exposes distinct backend health states", () => {
  assert.equal(serviceHealthState(undefined, true, false), "UNKNOWN");
  assert.equal(serviceHealthState(undefined, false, true), "UNAVAILABLE");
  assert.equal(serviceHealthState("OK", false, false), "HEALTHY");
  assert.equal(serviceHealthState("maintenance", false, false), "DEGRADED");
});

test("execution metrics report unavailable values when there are no runs", () => {
  assert.deepEqual(executionMetrics([]), {
    total: 0,
    succeeded: 0,
    failed: 0,
    averageRuntimeMs: null,
    successRatePercent: null,
  });
});

test("execution metrics use the actual reported statuses and runtimes", () => {
  assert.deepEqual(executionMetrics([
    { status: "SUCCEEDED", execution_time_ms: 100 },
    { status: "FAILED", execution_time_ms: 300 },
    { status: "RUNNING", execution_time_ms: null },
  ]), {
    total: 3,
    succeeded: 1,
    failed: 1,
    averageRuntimeMs: 200,
    successRatePercent: 33,
  });
});
