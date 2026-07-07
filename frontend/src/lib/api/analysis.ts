import { apiRequest } from "@/lib/api/client";
import { API } from "@/lib/api/endpoints";

export interface AnalyzeStartResponse {
  execution_id: string;
  upload_id: string;
  status: string;
}

export function startAnalysis(uploadId: string, sector?: string | null, signal?: AbortSignal) {
  return apiRequest<AnalyzeStartResponse>(
    API.analyze,
    {
      method: "POST",
      body: JSON.stringify({
        upload_id: uploadId,
        sector: sector || undefined,
        mode: "auto",
        explain: true,
        include_reports: true,
      }),
    },
    signal,
  );
}
