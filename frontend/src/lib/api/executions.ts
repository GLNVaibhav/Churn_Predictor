import { apiRequest } from "@/lib/api/client";
import { API } from "@/lib/api/endpoints";

export type ExecutionStatus = "PENDING" | "RUNNING" | "SUCCEEDED" | "SUCCESS" | "FAILED" | "CANCELLED";

export interface ExecutionSummaryResponse {
  execution_id: string;
  status: ExecutionStatus;
  created_at?: string;
  started_at?: string;
  completed_at?: string | null;
  execution_time_ms?: number | null;
  filename?: string | null;
  sector?: string | null;
  progress?: number | null;
}

export interface ExecutionDetailResponse {
  execution: Record<string, unknown>;
}

export interface PipelineStateResponse {
  pipeline_state: Record<string, unknown>;
}

export interface PredictionsResponse {
  predictions: Record<string, unknown>[];
}

export interface DecisionResponse {
  decision: Record<string, unknown>;
}

export interface ContextResponse {
  context: Record<string, unknown>;
}

export interface EventsResponse {
  events: Record<string, unknown>[];
}

export const isExecutionActive = (status?: string | null) =>
  status === "PENDING" || status === "RUNNING";

export function listExecutions(signal?: AbortSignal) {
  return apiRequest<ExecutionSummaryResponse[]>(API.executions, {}, signal);
}

export function getExecution(executionId: string, signal?: AbortSignal) {
  return apiRequest<ExecutionDetailResponse>(API.execution(executionId), {}, signal);
}

export function getExecutionPipeline(executionId: string, signal?: AbortSignal) {
  return apiRequest<PipelineStateResponse>(API.pipeline(executionId), {}, signal);
}

export function getExecutionPredictions(executionId: string, signal?: AbortSignal) {
  return apiRequest<PredictionsResponse>(API.predictions(executionId), {}, signal);
}

export function getExecutionDecision(executionId: string, signal?: AbortSignal) {
  return apiRequest<DecisionResponse>(API.decision(executionId), {}, signal);
}

export function getExecutionContext(executionId: string, signal?: AbortSignal) {
  return apiRequest<ContextResponse>(API.context(executionId), {}, signal);
}

export function getExecutionEvents(executionId: string, signal?: AbortSignal) {
  return apiRequest<EventsResponse>(API.events(executionId), {}, signal);
}
