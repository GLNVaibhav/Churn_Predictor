"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { MetricCard } from "@/components/shared/metric-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ErrorBanner, EmptyState, LoadingState } from "@/components/shared/query-states";
import { useExecutionContext } from "@/lib/context/execution-context";
import { useStartExecution, useUploadDataset } from "@/lib/hooks/use-execution";
import { mapUploadPreview } from "@/lib/api/live-transform";
import { sectorLabel } from "@/lib/constants/sectors";
import { cn } from "@/lib/utils";
import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  DatabaseZap,
  FileJson,
  FileSpreadsheet,
  Gauge,
  Route,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";

const STEPS = ["Dataset", "Preview", "Industry", "Readiness", "Execute"] as const;
const INDUSTRIES = ["telecom", "banking", "ecommerce", "healthcare"] as const;

const typeStyles: Record<string, string> = {
  numeric: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-200 dark:border-blue-800",
  categorical: "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950/40 dark:text-violet-200 dark:border-violet-800",
  boolean: "bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-200 dark:border-teal-800",
  text: "bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900 dark:text-slate-200 dark:border-slate-700",
  date: "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/40 dark:text-orange-200 dark:border-orange-800",
};

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const context = useExecutionContext();
  const upload = useUploadDataset();
  const analyze = useStartExecution();
  const [progress, setProgress] = useState(0);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [contextError, setContextError] = useState<string | null>(null);
  const [selectedSector, setSelectedSector] = useState<string>("telecom");
  const [routingMode, setRoutingMode] = useState<"auto" | "manual">("manual");
  const [businessContextText, setBusinessContextText] = useState("");
  const [step, setStep] = useState(0);
  const submissionLockRef = useRef(false);

  const preview = useMemo(() => (upload.data ? mapUploadPreview(upload.data) : null), [upload.data]);
  const maxStep = preview ? 4 : 0;
  const contextValid = useMemo(() => {
    if (!businessContextText.trim()) return false;
    try {
      const parsed = JSON.parse(businessContextText);
      return Boolean(parsed && !Array.isArray(parsed) && typeof parsed === "object");
    } catch {
      return false;
    }
  }, [businessContextText]);
  const contextSignalCount = useMemo(() => {
    if (!businessContextText.trim()) return 0;
    try {
      const parsed = JSON.parse(businessContextText);
      return Array.isArray(parsed?.events) ? parsed.events.length : Object.keys(parsed || {}).length;
    } catch {
      return 0;
    }
  }, [businessContextText]);
  const preflightChecks = useMemo(
    () => [
      { label: "CSV parsed", complete: Boolean(preview), detail: preview ? `${preview.rowCount.toLocaleString()} rows detected` : "Upload a customer CSV" },
      { label: "Semantic mappings found", complete: Boolean(preview && preview.columnCount > 0 && preview.detectionConfidence > 0), detail: preview ? `${preview.detectionConfidence}% domain confidence` : "Waiting for schema scan" },
      { label: "Context loaded", complete: contextValid, detail: contextValid ? `${contextSignalCount} business signals ready` : "Add a valid ABIL JSON context" },
    ],
    [contextSignalCount, contextValid, preview],
  );
  const preflightReady = preflightChecks.every((item) => item.complete);

  useEffect(() => {
    if (preview?.detectedSector && routingMode === "auto") setSelectedSector(preview.detectedSector);
  }, [preview?.detectedSector, routingMode]);

  function validate(file: File) {
    if (!file.name.toLowerCase().endsWith(".csv")) return "Only CSV files are supported.";
    if (file.size === 0) return "The selected CSV is empty.";
    return null;
  }

  function handleFile(file?: File) {
    if (!file || upload.isPending || submissionLockRef.current) return;
    const error = validate(file);
    setValidationError(error);
    if (error) return;
    setProgress(0);
    setContextError(null);
    upload.mutate({ file, onProgress: setProgress }, { onSuccess: () => setStep(1) });
  }

  function handleContextFile(file?: File) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setBusinessContextText(String(reader.result || ""));
      setContextError(null);
    };
    reader.readAsText(file);
  }

  async function runAnalysis() {
    if (submissionLockRef.current || analyze.isPending) return;

    let businessContext: Record<string, unknown> | null = null;
    const trimmed = businessContextText.trim();
    if (trimmed) {
      try {
        const parsed = JSON.parse(trimmed);
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Context JSON must be an object.");
        businessContext = parsed as Record<string, unknown>;
        setContextError(null);
      } catch (error) {
        setContextError(error instanceof Error ? error.message : "Invalid JSON context.");
        return;
      }
    }

    submissionLockRef.current = true;
    setStep(4);
    context.setExecutionContext({ sector: selectedSector });

    try {
      await analyze.mutateAsync({ sector: selectedSector, businessContext });
      router.push("/workspace");
    } finally {
      submissionLockRef.current = false;
    }
  }

  return (
    <PageShell>
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-4">
          <SectionCard title="Analysis Intake" description="Prepare a customer churn analysis">
            <div className="space-y-2">
              {STEPS.map((label, idx) => {
                const available = idx <= maxStep;
                const active = step === idx;
                return (
                  <button
                    key={label}
                    type="button"
                    disabled={!available}
                    onClick={() => available && setStep(idx)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left text-sm transition-colors",
                      active ? "border-primary bg-primary/10 text-foreground" : "border-border bg-background hover:bg-muted",
                      !available && "cursor-not-allowed opacity-45 hover:bg-background",
                    )}
                  >
                    <span className={cn("flex h-6 w-6 items-center justify-center rounded-md border text-xs", active && "border-primary bg-primary text-primary-foreground")}>
                      {idx < step ? <CheckCircle2 className="h-3.5 w-3.5" /> : idx + 1}
                    </span>
                    <span className="font-medium">{label}</span>
                  </button>
                );
              })}
            </div>
          </SectionCard>

          {preview ? (
            <SectionCard title="Execution Controls" description="Shown after CSV parsing">
              <div className="space-y-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Routing mode</p>
                  <div className="mt-2 grid grid-cols-2 gap-2 rounded-md bg-muted/45 p-1">
                    {[
                      ["manual", "Manual Override"],
                      ["auto", "Auto-Route"],
                    ].map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => {
                          setRoutingMode(value as "auto" | "manual");
                          if (value === "auto" && preview?.detectedSector) setSelectedSector(preview.detectedSector);
                        }}
                        className={cn(
                          "rounded-md px-2 py-1.5 text-xs font-semibold transition-colors",
                          routingMode === value
                            ? "bg-card text-foreground shadow-sm ring-1 ring-border/70"
                            : "text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Industry</p>
                  <Select value={selectedSector} onValueChange={(value) => value && setSelectedSector(value)}>
                    <SelectTrigger className="mt-2 bg-background">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {INDUSTRIES.map((industry) => (
                        <SelectItem key={industry} value={industry}>
                          {sectorLabel(industry)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    {routingMode === "manual"
                      ? "Manual selection will be used for this run."
                      : `Auto-route is using ${sectorLabel(preview?.detectedSector || selectedSector)} from dataset detection.`}
                  </p>
                </div>
                <label className="flex cursor-pointer items-center justify-between rounded-md border border-border bg-background px-3 py-2 text-sm hover:bg-muted">
                  <span className="flex items-center gap-2 font-medium"><FileJson className="h-4 w-4 text-primary" />Load ABIL context</span>
                  <span className="text-xs text-muted-foreground">{contextSignalCount} signals</span>
                  <input type="file" accept=".json,application/json" className="hidden" onChange={(event) => handleContextFile(event.target.files?.[0])} />
                </label>
              </div>
            </SectionCard>
          ) : (
            <SectionCard title="Next Step" description="Unlock after CSV parsing">
              <div className="rounded-lg border border-dashed border-border bg-muted/20 p-4 text-sm text-muted-foreground">
                Routing, industry selection, and ABIL context controls appear after the dataset schema is parsed.
              </div>
            </SectionCard>
          )}
        </div>

        <div className="space-y-5">
          <div className="premium-panel overflow-hidden">
            <div className="grid lg:grid-cols-[minmax(0,1fr)_340px]">
              <div className="p-6">
                <p className="text-xs font-semibold uppercase tracking-widest text-primary">New Run</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">Upload customer data and generate churn intelligence</h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
                  Build a clean analysis workspace from a CSV, with explicit industry control and optional business context for ABIL evidence.
                </p>
              </div>
              <div className="border-t border-border bg-muted/25 p-6 lg:border-l lg:border-t-0">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-border bg-card px-3 py-2">
                    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <DatabaseZap className="h-3.5 w-3.5 text-primary" />
                      Dataset
                    </div>
                    <p className="mt-1 text-sm font-semibold">{preview ? "Ready" : "Waiting"}</p>
                  </div>
                  <div className="rounded-lg border border-border bg-card px-3 py-2">
                    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <Route className="h-3.5 w-3.5 text-primary" />
                      Industry
                    </div>
                    <p className="mt-1 text-sm font-semibold">{selectedSector ? sectorLabel(selectedSector) : "-"}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <SectionCard title="Dataset" description="Upload a CSV file for churn analysis">
            <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => handleFile(event.target.files?.[0])} />
            <div
              className="flex min-h-56 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/25 px-6 py-10 text-center transition-colors hover:border-primary/40 hover:bg-muted/35"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                handleFile(event.dataTransfer.files?.[0]);
              }}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-border bg-card text-primary">
                <UploadCloud className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm font-semibold">Drop a customer dataset here</p>
                <p className="mt-1 text-xs text-muted-foreground">CSV only. The workspace will preview fields, industry fit, and analysis readiness.</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()} disabled={upload.isPending}>Browse files</Button>
            </div>
            {validationError ? <ErrorBanner error={new Error(validationError)} /> : null}
            {upload.isPending ? (
              <div className="mt-4">
                <LoadingState label={`Uploading ${progress}%`} />
                <Progress value={progress} className="mt-2 h-2" />
              </div>
            ) : null}
            {upload.error ? <ErrorBanner error={upload.error} onRetry={() => upload.reset()} /> : null}
          </SectionCard>

          {preview ? (
            <>
              <div className="grid gap-3 sm:grid-cols-4">
                <MetricCard label="Rows" value={preview.rowCount.toLocaleString()} icon={FileSpreadsheet} />
                <MetricCard label="Columns" value={String(preview.columnCount)} icon={BrainCircuit} />
                <MetricCard label="Detected" value={sectorLabel(preview.detectedSector)} icon={ShieldCheck} />
                <MetricCard label="Confidence" value={`${preview.detectionConfidence}%`} icon={Gauge} />
              </div>

              <SectionCard title="Data Preview" description="Detected columns, data types, and sample values">
                <div className="overflow-hidden rounded-md border border-border/60">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                      <tr><th className="px-4 py-2">Column</th><th className="px-4 py-2">Type</th><th className="px-4 py-2">Null %</th><th className="px-4 py-2">Samples</th></tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {preview.columns.slice(0, 12).map((col) => (
                        <tr key={col.name} className="hover:bg-muted/30">
                          <td className="px-4 py-2 font-mono text-xs">{col.name}</td>
                          <td className="px-4 py-2"><Badge variant="outline" className={typeStyles[col.inferredType]}>{col.inferredType}</Badge></td>
                          <td className="px-4 py-2 tabular-nums">{col.nullPercentage}%</td>
                          <td className="max-w-sm truncate px-4 py-2 text-xs text-muted-foreground">{col.sampleValues.join(", ") || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SectionCard>

              <SectionCard title="Business Context" description="ABIL JSON required for decision-aware execution">
                <details className="group rounded-lg border border-border bg-muted/20" open={!contextValid}>
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium">
                    <span>Advanced context payload</span>
                    <span className="text-xs text-muted-foreground">{contextSignalCount} signals</span>
                  </summary>
                  <div className="border-t border-border p-4">
                    <textarea
                      value={businessContextText}
                      onChange={(event) => {
                        setBusinessContextText(event.target.value);
                        setContextError(null);
                      }}
                      placeholder='{"events":[{"category":"Business Objective","description":"Retain premium customers","severity":"HIGH"}]}'
                      className="min-h-36 w-full resize-y rounded-md border border-border bg-background p-3 font-mono text-xs outline-none transition-colors focus:border-primary"
                    />
                    {contextError ? <p className="mt-2 text-xs text-destructive">{contextError}</p> : null}
                  </div>
                </details>
              </SectionCard>

              <SectionCard title="Preflight Checklist" description="Execution unlocks when the run is ready">
                <div className="grid gap-2">
                  {preflightChecks.map((item) => (
                    <div key={item.label} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2">
                      <div className="flex items-center gap-3">
                        <span className={cn("flex h-6 w-6 items-center justify-center rounded-full border", item.complete ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-border bg-muted text-muted-foreground")}>
                          {item.complete ? <CheckCircle2 className="h-3.5 w-3.5" /> : <span className="h-1.5 w-1.5 rounded-full bg-current" />}
                        </span>
                        <div>
                          <p className="text-sm font-medium">{item.label}</p>
                          <p className="text-xs text-muted-foreground">{item.detail}</p>
                        </div>
                      </div>
                      <Badge variant="outline" className={item.complete ? "border-emerald-200 bg-emerald-50 text-emerald-800" : ""}>
                        {item.complete ? "Ready" : "Waiting"}
                      </Badge>
                    </div>
                  ))}
                </div>
              </SectionCard>

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-4">
                <div>
                  <p className="text-sm font-semibold">Ready to execute</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {preview.fileName} will run as {sectorLabel(selectedSector)} using {routingMode === "manual" ? "manual override" : "auto-route"} with {contextSignalCount} business context signals.
                  </p>
                </div>
                <Button onClick={runAnalysis} disabled={!context.uploadId || !preflightReady || analyze.isPending || submissionLockRef.current}>
                  {analyze.isPending ? "Starting..." : "Execute Run"}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
              {analyze.error ? <ErrorBanner error={analyze.error} /> : null}
            </>
          ) : step > 0 ? (
            <EmptyState title="Upload required" description="Upload a CSV to continue." />
          ) : null}
        </div>
      </div>
    </PageShell>
  );
}
