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
import { Input } from "@/components/ui/input";
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

function isBusinessContextDocument(value: unknown, expectedSector?: string) {
  if (!value || Array.isArray(value) || typeof value !== "object") return false;
  const document = value as Record<string, unknown>;
  if (document.sector !== undefined &&
      (typeof document.sector !== "string" ||
       (expectedSector && normalizeSector(document.sector) !== normalizeSector(expectedSector)))) return false;
  if (!Array.isArray(document.events) || document.events.length < 1 || document.events.length > 100) return false;
  return document.events.every((item) => {
    if (!item || Array.isArray(item) || typeof item !== "object") return false;
    const event = item as Record<string, unknown>;
    return typeof event.category === "string" && Boolean(event.category.trim()) &&
      typeof event.description === "string" && Boolean(event.description.trim()) &&
      typeof event.severity === "string" &&
      ["LOW", "MEDIUM", "HIGH", "CRITICAL"].includes(event.severity.toUpperCase()) &&
      typeof event.confidence === "number" && Number.isFinite(event.confidence) &&
      event.confidence >= 0 && event.confidence <= 1 &&
      (event.affected_segments === undefined ||
        (Array.isArray(event.affected_segments) && event.affected_segments.every((segment) => typeof segment === "string"))) &&
      (event.source === undefined || typeof event.source === "string") &&
      (event.recommendation === undefined || typeof event.recommendation === "string") &&
      (event.recommended_action === undefined || typeof event.recommended_action === "string") &&
      (event.department === undefined || typeof event.department === "string") &&
      (event.priority === undefined || (Number.isInteger(event.priority) && Number(event.priority) >= 1 && Number(event.priority) <= 5)) &&
      (event.timestamp === undefined || typeof event.timestamp === "string");
  });
}

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const executionControlsRef = useRef<HTMLDivElement>(null);
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
  const [businessContextCategory, setBusinessContextCategory] = useState("");
  const [businessContextSeverity, setBusinessContextSeverity] = useState("");
  const [businessContextConfidence, setBusinessContextConfidence] = useState("");
  const [businessContextDocument, setBusinessContextDocument] = useState<Record<string, unknown> | null>(null);
  const [businessContextFileName, setBusinessContextFileName] = useState<string | null>(null);
  const [businessContextMode, setBusinessContextMode] = useState<"text" | "json">("text");
  const [step, setStep] = useState(0);
  const [browserFileSize, setBrowserFileSize] = useState<number | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const submissionLockRef = useRef(false);
  const reduceMotion = useReducedMotion();

  const preview = useMemo(() => (upload.data ? mapUploadPreview(upload.data) : null), [upload.data]);
  const maxStep = preview ? 4 : 0;
  const contextValid = useMemo(() => {
    if (businessContextMode === "json") {
      return businessContextDocument
        ? isBusinessContextDocument(businessContextDocument, selectedSector)
        : false;
    }
    const hasTypedContext = Boolean(
      businessContextText.trim() || businessContextCategory.trim() ||
      businessContextSeverity || businessContextConfidence,
    );
    if (!hasTypedContext) return false;
    const confidence = Number(businessContextConfidence);
    return Boolean(
      businessContextText.trim() &&
      businessContextCategory.trim() &&
      ["LOW", "MEDIUM", "HIGH", "CRITICAL"].includes(businessContextSeverity) &&
      businessContextConfidence.trim() &&
      Number.isFinite(confidence) && confidence >= 0 && confidence <= 1,
    );
  }, [businessContextCategory, businessContextConfidence, businessContextDocument, businessContextMode, businessContextSeverity, businessContextText, selectedSector]);
  const hasContextInput = businessContextMode === "json"
    ? Boolean(businessContextDocument)
    : Boolean(businessContextText.trim() || businessContextCategory.trim() || businessContextSeverity || businessContextConfidence);
  const contextSignalCount = useMemo(() => {
    if (businessContextMode === "json") {
      const events = businessContextDocument?.events;
      return Array.isArray(events) ? events.length : 0;
    }
    return businessContextText.trim() ? 1 : 0;
  }, [businessContextDocument, businessContextMode, businessContextText]);
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
        complete: !hasContextInput || contextValid,
        detail: contextValid
          ? `${contextSignalCount} ABIL context item${contextSignalCount === 1 ? "" : "s"} ready for this execution`
          : hasContextInput
            ? "Complete the typed context details or choose a valid JSON file"
            : "No context supplied; analysis can continue without ABIL",
      },
    ],
    [contextSignalCount, contextValid, hasContextInput, preview, routingMode, selectedSector],
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
    if (!file.name.toLowerCase().endsWith(".json") || file.size > 1024 * 1024) {
      setContextError("Choose a JSON file no larger than 1 MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed: unknown = JSON.parse(String(reader.result || ""));
        if (!isBusinessContextDocument(parsed)) throw new Error("The file must contain one or more valid ABIL events.");
        setBusinessContextDocument(parsed as Record<string, unknown>);
        setBusinessContextFileName(file.name);
        setBusinessContextMode("json");
        setContextError(null);
      } catch (error) {
        setBusinessContextDocument(null);
        setBusinessContextFileName(null);
        setContextError(error instanceof Error ? error.message : "Could not read this JSON file.");
      }
    };
    reader.onerror = () => setContextError("Could not read this JSON file.");
    reader.readAsText(file);
  }

  function configureAnalysis() {
    setStep(2);
    requestAnimationFrame(() => {
      executionControlsRef.current?.scrollIntoView({
        behavior: reduceMotion ? "auto" : "smooth",
        block: "center",
      });
      executionControlsRef.current?.focus({ preventScroll: true });
    });
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

    let businessContext: Record<string, unknown> | undefined;
    if (hasContextInput && !contextValid) {
      setContextError("Complete the business context fields or choose a valid JSON file before continuing.");
      return;
    }
    if (contextValid && businessContextMode === "json" && businessContextDocument) {
      const events = (businessContextDocument.events as Record<string, unknown>[]).map((event) => ({
        ...event,
        severity: String(event.severity).toUpperCase(),
      }));
      businessContext = { ...businessContextDocument, sector: selectedSector, events };
    } else if (contextValid && businessContextMode === "text") {
      businessContext = {
        sector: selectedSector,
        events: [{
          category: businessContextCategory.trim(),
          description: businessContextText.trim(),
          severity: businessContextSeverity,
          confidence: Number(businessContextConfidence),
          source: "user_supplied_text",
        }],
      };
    }
    setContextError(null);

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
            <div ref={executionControlsRef} id="analysis-controls" tabIndex={-1} className="rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">
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
                  <span className="flex items-center gap-2 font-medium"><FileJson className="h-4 w-4 text-primary" />Load ABIL JSON file</span>
                  <span className="text-xs text-muted-foreground">{contextSignalCount} signals</span>
                  <input type="file" accept=".json,application/json" className="hidden" onChange={(event) => handleContextFile(event.target.files?.[0])} />
                </label>
                {businessContextFileName ? <p className="text-xs text-muted-foreground">Loaded: {businessContextFileName}</p> : null}
              </div>
            </SectionCard>
            </div>
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
              <DatasetIntelligence profile={preview} browserFileSize={browserFileSize} onBack={() => setStep(0)} onContinue={configureAnalysis} />

              <SectionCard title="Business Context" description="Add ABIL context as plain text or load a structured JSON file. Context informs decision support and does not change model predictions.">
                <div className="space-y-4">
                  <div className="inline-flex rounded-md bg-muted/50 p-1" role="tablist" aria-label="Business context input format">
                    <button type="button" role="tab" aria-selected={businessContextMode === "text"} onClick={() => { setBusinessContextMode("text"); setContextError(null); }} className={cn("rounded px-3 py-1.5 text-sm font-medium transition-colors", businessContextMode === "text" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>Type context</button>
                    <button type="button" role="tab" aria-selected={businessContextMode === "json"} onClick={() => { setBusinessContextMode("json"); setContextError(null); }} className={cn("rounded px-3 py-1.5 text-sm font-medium transition-colors", businessContextMode === "json" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>Use JSON file</button>
                  </div>
                  {businessContextMode === "text" ? (
                    <div className="space-y-3">
                      <label className="block space-y-1.5 text-sm font-medium">
                        <span>Context type</span>
                        <Input value={businessContextCategory} onChange={(event) => { setBusinessContextCategory(event.target.value); setContextError(null); }} placeholder="e.g. Business objective or service disruption" />
                      </label>
                      <label className="block space-y-1.5 text-sm font-medium">
                        <span>Business context</span>
                        <textarea value={businessContextText} onChange={(event) => { setBusinessContextText(event.target.value); setContextError(null); }} placeholder="Describe the current business situation or event..." className="min-h-28 w-full resize-y rounded-md border border-border bg-background p-3 text-sm outline-none transition-colors focus:border-primary" />
                      </label>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <label className="block space-y-1.5 text-sm font-medium">
                          <span>Severity</span>
                          <Select value={businessContextSeverity} onValueChange={(value) => { if (value) { setBusinessContextSeverity(value); setContextError(null); } }}>
                            <SelectTrigger><SelectValue placeholder="Select severity" /></SelectTrigger>
                            <SelectContent>
                              {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((value) => <SelectItem key={value} value={value}>{value[0] + value.slice(1).toLowerCase()}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </label>
                        <label className="block space-y-1.5 text-sm font-medium">
                          <span>Confidence (0–1)</span>
                          <Input type="number" min="0" max="1" step="0.01" value={businessContextConfidence} onChange={(event) => { setBusinessContextConfidence(event.target.value); setContextError(null); }} placeholder="Enter your confidence" />
                        </label>
                      </div>
                      <p className="text-xs leading-5 text-muted-foreground">Severity and confidence are supplied by you as decision-support context. They do not alter churn predictions.</p>
                    </div>
                  ) : businessContextDocument ? (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">{businessContextFileName || "ABIL JSON context"}</p>
                      <pre className="max-h-56 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-xs">{JSON.stringify(businessContextDocument, null, 2)}</pre>
                      {!contextValid ? <p className="text-xs text-destructive">Check the JSON events and ensure its sector matches the selected industry.</p> : null}
                    </div>
                  ) : (
                    <p className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">Choose “Load ABIL JSON file” in Execution Controls to attach a structured context document.</p>
                  )}
                  {contextError ? <p role="alert" className="text-sm text-destructive">{contextError}</p> : null}
                  {businessContextMode === "text" && hasContextInput && !contextValid && !contextError ? <p className="text-sm text-destructive">Complete all context fields, including severity and confidence, or clear them to continue without ABIL context.</p> : null}
                </div>
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
                    {preview.fileName} will run {routingMode === "manual" ? `as ${sectorLabel(selectedSector)} using manual override` : `using automatic ${preview.detectedSector ? sectorLabel(preview.detectedSector) : "unconfirmed sector"} routing`}. {contextValid ? `${contextSignalCount} ABIL context item${contextSignalCount === 1 ? "" : "s"} will inform decision support only;` : "No ABIL context is attached;"} model predictions remain independent of business context.
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
