"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { DatasetIntelligence } from "@/components/upload/dataset-intelligence";
import AttractButton from "@/components/kokonutui/attract-button";
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
  CheckCircle2,
  DatabaseZap,
  FileJson,
  Route,
  UploadCloud,
} from "lucide-react";

const STEPS = ["Dataset", "Preview", "Industry", "Readiness", "Execute"] as const;
const INDUSTRIES = ["telecom", "banking", "ecommerce", "healthcare"] as const;
const normalizeSector = (value: string) => {
  const normalized = value.trim().toLowerCase();
  return normalized === "retail" || normalized === "e-commerce" ? "ecommerce" : normalized;
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
  const [selectedSector, setSelectedSector] = useState<string>("");
  const [routingMode, setRoutingMode] = useState<"auto" | "manual">("auto");
  const [businessContextText, setBusinessContextText] = useState("");
  const [step, setStep] = useState(0);
  const [browserFileSize, setBrowserFileSize] = useState<number | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const submissionLockRef = useRef(false);
  const reduceMotion = useReducedMotion();

  const preview = useMemo(() => (upload.data ? mapUploadPreview(upload.data) : null), [upload.data]);
  const maxStep = preview ? 4 : 0;
  const contextValid = useMemo(() => {
    if (!businessContextText.trim()) return false;
    try {
      const parsed = JSON.parse(businessContextText);
      return Boolean(
        parsed && !Array.isArray(parsed) && typeof parsed === "object" &&
        (!parsed.sector || (typeof parsed.sector === "string" && normalizeSector(parsed.sector) === normalizeSector(selectedSector))) &&
        Array.isArray(parsed.events) && parsed.events.length > 0 &&
        parsed.events.every((event: Record<string, unknown>) =>
          typeof event.category === "string" && event.category.trim() &&
          typeof event.description === "string" && event.description.trim() &&
          ["LOW", "MEDIUM", "HIGH", "CRITICAL"].includes(String(event.severity).toUpperCase()) &&
          typeof event.confidence === "number" && event.confidence >= 0 && event.confidence <= 1 &&
          (event.affected_segments === undefined || (Array.isArray(event.affected_segments) && event.affected_segments.every((segment) => typeof segment === "string"))) &&
          (event.source === undefined || typeof event.source === "string") &&
          (event.recommendation === undefined || typeof event.recommendation === "string") &&
          (event.recommended_action === undefined || typeof event.recommended_action === "string") &&
          (event.department === undefined || typeof event.department === "string") &&
          (event.priority === undefined || (Number.isInteger(event.priority) && Number(event.priority) >= 1 && Number(event.priority) <= 5)) &&
          (event.timestamp === undefined || typeof event.timestamp === "string")
        )
      );
    } catch {
      return false;
    }
  }, [businessContextText, selectedSector]);
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
      { label: "Dataset schema available", complete: Boolean(preview && preview.columnCount > 0), detail: preview ? `${preview.columnCount} columns returned by the upload API` : "Waiting for schema scan" },
      {
        label: "Sector selection",
        complete: routingMode === "manual" ? Boolean(selectedSector) : Boolean(preview?.detectedSector),
        detail: routingMode === "manual"
          ? selectedSector ? `Manual override: ${sectorLabel(selectedSector)}` : "Choose an industry for manual routing"
          : preview?.detectedSector ? `Detected: ${sectorLabel(preview.detectedSector)}` : "Automatic sector is uncertain; choose Manual Override and confirm an industry",
      },
      {
        label: "Context preview (optional)",
        complete: true,
        detail: contextValid
          ? `${contextSignalCount} ABIL signals validated for this execution`
          : businessContextText.trim()
            ? "Context must contain one or more events with category, description, severity, and confidence from 0 to 1"
            : "No context supplied; analysis can continue without ABIL",
      },
    ],
    [businessContextText, contextSignalCount, contextValid, preview, routingMode, selectedSector],
  );
  const preflightReady = preflightChecks.every((item) => item.complete);

  useEffect(() => {
    if (preview?.detectedSector && routingMode === "auto") setSelectedSector(preview.detectedSector);
  }, [preview?.detectedSector, routingMode]);

  function validate(file: File) {
    if (!file.name.toLowerCase().endsWith(".csv")) return "Only CSV files are supported.";
    if (file.size === 0) return "The selected CSV is empty.";
    if (file.size > 10 * 1024 * 1024) return "CSV files must be 10 MB or smaller.";
    return null;
  }

  function handleFile(file?: File) {
    if (!file || upload.isPending || submissionLockRef.current) return;
    const error = validate(file);
    setValidationError(error);
    if (error) return;
    setProgress(0);
    setContextError(null);
    upload.mutate({ file, onProgress: setProgress }, { onSuccess: () => { setBrowserFileSize(file.size); setStep(1); } });
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
    if (routingMode === "auto" && !preview?.detectedSector) {
      setContextError("Automatic sector detection is uncertain. Choose Manual Override and select the industry to continue.");
      return;
    }
    if (!selectedSector) {
      setContextError("Select an industry before starting analysis.");
      return;
    }

    const trimmed = businessContextText.trim();
    let businessContext: Record<string, unknown> | undefined;
    if (trimmed) {
      try {
        const parsed = JSON.parse(trimmed);
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Context JSON must be an object.");
        if (!contextValid) throw new Error("Context schema is invalid or its sector does not match the selected analysis sector.");
        const events = (parsed.events as Record<string, unknown>[]).map((event) => ({
          ...event,
          severity: String(event.severity).toUpperCase(),
        }));
        businessContext = { ...parsed, events } as Record<string, unknown>;
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
      // The UI's manual option means an explicit sector model. The backend
      // accepts only `sector`, `universal`, or `auto` as execution modes.
      await analyze.mutateAsync({
        sector: routingMode === "manual" ? selectedSector : undefined,
        mode: routingMode === "manual" ? "sector" : "auto",
        businessContext,
      });
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
                  <Select value={selectedSector || undefined} onValueChange={(value) => value && setSelectedSector(value)}>
                    <SelectTrigger className="mt-2 bg-background">
                      <SelectValue placeholder="Select an industry" />
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
                      : preview?.detectedSector
                        ? `Automatic routing detected ${sectorLabel(preview.detectedSector)}. The backend will independently detect the schema for execution.`
                        : "Automatic routing is unavailable for this schema. Confirm an industry using Manual Override."}
                  </p>
                </div>
                <label className="flex cursor-pointer items-center justify-between rounded-md border border-border bg-background px-3 py-2 text-sm hover:bg-muted">
                  <span className="flex items-center gap-2 font-medium"><FileJson className="h-4 w-4 text-primary" />Load context preview JSON</span>
                  <span className="text-xs text-muted-foreground">{contextSignalCount} signals</span>
                  <input type="file" accept=".json,application/json" className="hidden" onChange={(event) => handleContextFile(event.target.files?.[0])} />
                </label>
              </div>
            </SectionCard>
          ) : (
            <SectionCard title="Next Step" description="Unlock after CSV parsing">
              <div className="rounded-lg border border-dashed border-border bg-muted/20 p-4 text-sm text-muted-foreground">
                Routing, industry selection, and an optional local context preview appear after the dataset schema is parsed.
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
                  Build a clean analysis workspace from a CSV with explicit industry selection and a transparent optional context preview.
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
            <motion.div
              className={cn("flex min-h-56 flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-10 text-center transition-colors", dragActive ? "border-foreground bg-muted/50" : "border-border bg-muted/15 hover:border-foreground/40 hover:bg-muted/30", upload.isPending && "pointer-events-none opacity-60")}
              animate={{ scale: dragActive ? 1.01 : 1 }}
              transition={{ duration: reduceMotion ? 0 : 0.16 }}
              onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }}
              onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragActive(false); }}
              onDragOver={(event) => { event.preventDefault(); setDragActive(true); }}
              onDrop={(event) => {
                event.preventDefault();
                setDragActive(false);
                handleFile(event.dataTransfer.files?.[0]);
              }}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-border bg-card text-primary">
                <UploadCloud className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm font-semibold">{dragActive ? "Release to inspect this CSV" : "Drop a customer dataset here"}</p>
                <p className="mt-1 text-xs text-muted-foreground">CSV only. The workspace will preview fields, industry fit, and analysis readiness.</p>
              </div>
              <AttractButton type="button" onClick={() => inputRef.current?.click()} disabled={upload.isPending} className="border border-border bg-foreground text-background hover:bg-foreground/90 dark:bg-foreground dark:text-background">Browse files</AttractButton>
            </motion.div>
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
              <DatasetIntelligence profile={preview} browserFileSize={browserFileSize} onBack={() => setStep(0)} onContinue={() => setStep(2)} />

              <SectionCard title="Business Context" description="Optional ABIL context is validated and associated with this analysis execution. It enriches decision support without changing model predictions.">
                <details className="group rounded-lg border border-border bg-muted/20" open={!contextValid}>
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium">
                    <span>Advanced context payload</span>
                    <span className="text-xs text-muted-foreground">{contextSignalCount} signals</span>
                  </summary>
                  <div className="border-t border-border p-4">
                    <p className="mb-3 text-xs leading-5 text-muted-foreground">Provide one or more business events. Severity and confidence are decision-support evidence only; context does not change customer churn predictions.</p>
                    <textarea
                      value={businessContextText}
                      onChange={(event) => {
                        setBusinessContextText(event.target.value);
                        setContextError(null);
                      }}
                      placeholder='{"events":[{"category":"Business Objective","description":"Retain premium customers","severity":"HIGH","confidence":0.85,"affected_segments":["Premium"]}]}'
                      className="min-h-36 w-full resize-y rounded-md border border-border bg-background p-3 font-mono text-xs outline-none transition-colors focus:border-primary"
                    />
                    {contextError ? <p className="mt-2 text-xs text-destructive">{contextError}</p> : businessContextText.trim() && !contextValid ? <p className="mt-2 text-xs text-destructive">Context must contain one or more valid ABIL events.</p> : null}
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
                    {preview.fileName} will run {routingMode === "manual" ? `as ${sectorLabel(selectedSector)} using manual override` : `using automatic ${preview.detectedSector ? sectorLabel(preview.detectedSector) : "unconfirmed sector"} routing`}. {contextValid ? `${contextSignalCount} ABIL signals will inform decision support only;` : "No ABIL context is attached;"} model predictions remain independent of business context.
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
