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
import { UploadCloud, FileSpreadsheet, ArrowRight } from "lucide-react";

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

  const preview = useMemo(() => (upload.data ? mapUploadPreview(upload.data) : null), [upload.data]);

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
    upload.mutate({ file, onProgress: setProgress });
  }

  async function runAnalysis() {
    const result = await analyze.mutateAsync();
    router.push("/pipeline");
    return result;
  }

  return (
    <PageShell>
      <SectionCard title="Upload a Dataset" description="Any schema shape is accepted; sector and field mapping are resolved downstream.">
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(event) => handleFile(event.target.files?.[0])}
        />
        <div
          className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border/70 bg-muted/20 px-6 py-12 text-center"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            handleFile(event.dataTransfer.files?.[0]);
          }}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <UploadCloud className="h-6 w-6 text-primary" />
          </div>
          <div>
            <p className="text-sm font-medium">Drag and drop a CSV file, or click to browse</p>
            <p className="mt-1 text-xs text-muted-foreground">Analysis starts only after you run it explicitly.</p>
          </div>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => inputRef.current?.click()}>
            Browse files
          </Button>
        </div>
        {validationError ? <div className="mt-4"><ErrorBanner error={new Error(validationError)} /></div> : null}
        {upload.isPending ? (
          <div className="mt-4">
            <LoadingState label={`Uploading ${progress}%`} />
            <Progress value={progress} className="mt-2 h-2" />
          </div>
        ) : null}
        {upload.error ? <div className="mt-4"><ErrorBanner error={upload.error} onRetry={() => upload.reset()} /></div> : null}
      </SectionCard>

      <SectionCard
        title="Last Uploaded Dataset"
        description="Preview returned by the live upload endpoint"
        action={
          <Button size="sm" onClick={runAnalysis} disabled={!context.uploadId || analyze.isPending}>
            {analyze.isPending ? "Starting..." : "Run Analysis"}
            <ArrowRight className="h-4 w-4" />
          </Button>
        }
      >
        {preview ? (
          <>
            <div className="flex flex-wrap items-center gap-4 rounded-lg border border-border/60 bg-muted/20 p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <FileSpreadsheet className="h-5 w-5 text-primary" />
              </div>
              <div className="min-w-[180px] flex-1">
                <p className="text-sm font-medium">{preview.fileName}</p>
                <p className="text-xs text-muted-foreground">
                  {preview.rowCount.toLocaleString()} rows · {preview.columnCount} columns
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted-foreground">Detected sector</p>
                <Badge variant="outline" className="mt-1 capitalize">
                  {preview.detectedSector} · {preview.detectionConfidence}% confidence
                </Badge>
              </div>
            </div>

            <div className="mt-5 overflow-hidden rounded-lg border border-border/60">
              <table className="w-full text-sm">
                <thead className="bg-muted/40">
                  <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2.5 font-medium">Column</th>
                    <th className="px-4 py-2.5 font-medium">Inferred Type</th>
                    <th className="px-4 py-2.5 font-medium">Null %</th>
                    <th className="px-4 py-2.5 font-medium">Sample Values</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {preview.columns.map((col) => (
                    <tr key={col.name}>
                      <td className="px-4 py-2.5 font-mono text-xs">{col.name}</td>
                      <td className="px-4 py-2.5">
                        <Badge variant="outline" className={typeStyles[col.inferredType]}>
                          {col.inferredType}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 tabular-nums">{col.nullPercentage}%</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{col.sampleValues.join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {analyze.error ? <div className="mt-4"><ErrorBanner error={analyze.error} /></div> : null}
          </>
        ) : (
          <EmptyState title="No dataset uploaded" description="Upload a CSV to receive the backend UploadResponse and enable analysis." />
        )}
      </SectionCard>
    </PageShell>
  );
}
