import { apiRequest, uploadWithProgress } from "@/lib/api/client";
import { API } from "@/lib/api/endpoints";

export interface UploadResponse {
  upload_id: string;
  status: string;
  filename: string;
  rows: number;
  columns: number;
  null_counts: Record<string, number>;
  dtypes: Record<string, string>;
  sector: string | null;
  coverage_score: number | null;
  concept_confidence: number | null;
  preview_rows?: Record<string, unknown>[];
  warnings?: string[];
  created_at: string;
}

export function uploadDataset(file: File, onProgress?: (progress: number) => void, signal?: AbortSignal) {
  const formData = new FormData();
  formData.append("file", file);
  return uploadWithProgress<UploadResponse>(API.upload, formData, onProgress, signal);
}

export function uploadDatasetFetch(file: File, signal?: AbortSignal) {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<UploadResponse>(API.upload, { method: "POST", body: formData }, signal);
}
