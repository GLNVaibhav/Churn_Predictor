"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ErrorBanner, EmptyState, LoadingState } from "@/components/shared/query-states";
import { useExecutionContext } from "@/lib/context/execution-context";
import { useStartExecution, useUploadDataset } from "@/lib/hooks/use-execution";
import { mapUploadPreview } from "@/lib/api/live-transform";
import { sectorLabel } from "@/lib/constants/sectors";
import { cn } from "@/lib/utils";
import { UploadCloud, FileSpreadsheet, ArrowRight, CheckCircle2 } from "lucide-react";

const STEPS = ["Dataset", "Preview", "Industry", "Coverage", "Validation", "Execute"] as const;

const typeStyles: Record<string, string> = {
  numeric: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  categorical: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  boolean: "bg-teal-500/10 text-teal-400 border-teal-500/20",
  text: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  date: "bg-orange-500/10 text-orange-400 border-orange-500/20",
};

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const context = useExecutionContext();
  const upload = useUploadDataset();
  const analyze = useStartExecution();
  const [progress, setProgress] = useState(0);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [step, setStep] = useState(0);

  const preview = useMemo(() => (upload.data ? mapUploadPreview(upload.data) : null), [upload.data]);

  const maxStep = preview ? 4 : upload.data ? 1 : 0;

  function validate(file: File) {
    if (!file.name.toLowerCase().endsWith(".csv")) return "Only CSV files are supported.";
    if (file.size === 0) return "The selected CSV is empty.";
    return null;
  }

  function handleFile(file?: File) {
    if (!file) return;
    const error = validate(file);
    setValidationError(error);
    if (error) return;
    setProgress(0);
    upload.mutate({ file, onProgress: setProgress }, {
      onSuccess: () => setStep(1),
    });
  }

  async function runAnalysis() {
    setStep(5);
    await analyze.mutateAsync();
    router.push("/workspace");
  }

  return (
    <PageShell>
      <div className="mb-6 flex flex-wrap items-center gap-2">
        {STEPS.map((label, idx) => (
          <button
            key={label}
            type="button"
            onClick={() => idx <= maxStep && setStep(idx)}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors",
              step === idx ? "bg-blue-500/20 text-blue-300" : idx <= maxStep ? "text-slate-300 hover:bg-white/5" : "text-slate-600"
            )}
          >
            {idx < step ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <span className="flex h-4 w-4 items-center justify-center rounded-full border text-[10px]">{idx + 1}</span>}
            {label}
          </button>
        ))}
      </div>

      {step === 0 ? (
        <SectionCard title="Step 1 — Dataset" description="Upload a CSV file. Schema mapping happens in the framework.">
          <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => handleFile(e.target.files?.[0])} />
          <div
            className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border/70 bg-muted/20 px-6 py-12 text-center"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); handleFile(e.dataTransfer.files?.[0]); }}
          >
            <UploadCloud className="h-10 w-10 text-primary" />
            <p className="text-sm font-medium">Drag and drop a CSV, or browse</p>
            <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>Browse files</Button>
          </div>
          {validationError ? <ErrorBanner error={new Error(validationError)} /> : null}
          {upload.isPending ? (<><LoadingState label={`Uploading ${progress}%`} /><Progress value={progress} className="mt-2 h-2" /></>) : null}
          {upload.error ? <ErrorBanner error={upload.error} onRetry={() => upload.reset()} /> : null}
        </SectionCard>
      ) : null}

      {step >= 1 && preview ? (
        <>
          {step === 1 ? (
            <SectionCard title="Step 2 — Preview" description="Column profiling from backend upload endpoint">
              <div className="overflow-hidden rounded-lg border border-border/60">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                    <tr><th className="px-4 py-2">Column</th><th className="px-4 py-2">Type</th><th className="px-4 py-2">Null %</th></tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {preview.columns.slice(0, 8).map((col) => (
                      <tr key={col.name}><td className="px-4 py-2 font-mono text-xs">{col.name}</td>
                        <td className="px-4 py-2"><Badge variant="outline" className={typeStyles[col.inferredType]}>{col.inferredType}</Badge></td>
                        <td className="px-4 py-2">{col.nullPercentage}%</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Button className="mt-4" size="sm" onClick={() => setStep(2)}>Continue</Button>
            </SectionCard>
          ) : null}

          {step === 2 ? (
            <SectionCard title="Step 3 — Industry Detection" description="Sector detected by universal_churn preprocessing">
              <div className="flex items-center gap-4 rounded-lg border border-border/60 p-4">
                <FileSpreadsheet className="h-8 w-8 text-primary" />
                <div>
                  <p className="font-medium">{preview.fileName}</p>
                  <Badge variant="outline" className="mt-1 capitalize">{sectorLabel(preview.detectedSector)} · {preview.detectionConfidence}%</Badge>
                </div>
              </div>
              <Button className="mt-4" size="sm" onClick={() => setStep(3)}>Continue</Button>
            </SectionCard>
          ) : null}

          {step === 3 ? (
            <SectionCard title="Step 4 — Coverage Preview" description="Framework coverage score from upload probe">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-border/60 p-4"><p className="text-xs text-muted-foreground">Coverage Score</p><p className="text-2xl font-semibold">{upload.data?.coverage_score != null ? `${(Number(upload.data.coverage_score) * 100).toFixed(1)}%` : "—"}</p></div>
                <div className="rounded-lg border border-border/60 p-4"><p className="text-xs text-muted-foreground">Concept Confidence</p><p className="text-2xl font-semibold">{upload.data?.concept_confidence != null ? `${(Number(upload.data.concept_confidence) * 100).toFixed(1)}%` : "—"}</p></div>
              </div>
              <Button className="mt-4" size="sm" onClick={() => setStep(4)}>Continue</Button>
            </SectionCard>
          ) : null}

          {step === 4 ? (
            <SectionCard title="Step 5 — Validation" description="Review before execution">
              <ul className="space-y-2 text-sm">
                <li>{preview.rowCount.toLocaleString()} rows · {preview.columnCount} columns</li>
                <li>Industry: {sectorLabel(preview.detectedSector)}</li>
                <li>Mode: Auto routing</li>
              </ul>
              <Button className="mt-4" size="sm" onClick={runAnalysis} disabled={!context.uploadId || analyze.isPending}>
                {analyze.isPending ? "Starting..." : "Execute Analysis"}<ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              {analyze.error ? <ErrorBanner error={analyze.error} /> : null}
            </SectionCard>
          ) : null}

          {step === 5 && analyze.isPending ? <LoadingState label="Starting analysis..." /> : null}
        </>
      ) : step > 0 && !preview ? (
        <EmptyState title="Upload required" description="Complete step 1 to continue the wizard." />
      ) : null}
    </PageShell>
  );
}
