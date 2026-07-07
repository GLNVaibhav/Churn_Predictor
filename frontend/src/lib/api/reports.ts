import { apiRequest } from "@/lib/api/client";
import { API } from "@/lib/api/endpoints";

export interface ReportsResponse {
  reports: Record<string, unknown>[];
}

export function getExecutionReports(executionId: string, signal?: AbortSignal) {
  return apiRequest<ReportsResponse>(API.reports(executionId), {}, signal);
}
