"use client";

import { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { RiskTierBadge, RoutingTierBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertTriangle, CheckCircle2, ClipboardCheck, Clock, Signal, XCircle } from "lucide-react";
import type { PredictionRecord } from "@/lib/types";
import { cn } from "@/lib/utils";

const sectorLabel: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  healthcare: "Healthcare",
  ecommerce: "E-commerce",
};

const decisionConfig: Record<PredictionRecord["decision"], { icon: typeof CheckCircle2; className: string }> = {
  Approved: { icon: CheckCircle2, className: "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/35 dark:text-emerald-200" },
  Escalate: { icon: AlertTriangle, className: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/35 dark:text-amber-200" },
  Refused: { icon: XCircle, className: "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/35 dark:text-red-200" },
};

function ContributionWaterfall({ record }: { record: PredictionRecord }) {
  const base = Math.max(12, Math.round(record.churnProbability * 38));
  const contributions = [
    { label: record.supportingEvidence[0] || "Recent engagement drop", value: Math.min(28, Math.max(8, Math.round(record.churnProbability * 24))), direction: "up" },
    { label: record.supportingEvidence[1] || "Weak retention signal", value: Math.min(18, Math.max(5, Math.round(record.churnProbability * 15))), direction: "up" },
    { label: "Coverage confidence", value: -Math.min(14, Math.max(4, Math.round(record.coverageScore / 10))), direction: "down" },
    { label: "Concept confidence", value: -Math.min(12, Math.max(3, Math.round(record.conceptConfidenceScore / 12))), direction: "down" },
  ];

  return (
    <div>
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Contribution Waterfall
      </p>
      <div className="rounded-lg border border-border bg-background p-3">
        <div className="mb-3 flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Base risk</span>
          <span className="font-semibold tabular-nums">{base}%</span>
        </div>
        <div className="space-y-3">
          {contributions.map((item) => {
            const width = Math.min(92, Math.abs(item.value) * 3);
            const up = item.direction === "up";
            return (
              <div key={item.label} className="grid gap-2">
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="truncate text-muted-foreground">{item.label}</span>
                  <span className={cn("font-semibold tabular-nums", up ? "text-red-800" : "text-emerald-800")}>
                    {up ? "+" : ""}{item.value}%
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-1">
                  <div className="flex justify-end">
                    {!up ? <div className="h-2 rounded-l-full bg-emerald-200" style={{ width: `${width}%` }} /> : null}
                  </div>
                  <div>
                    {up ? <div className="h-2 rounded-r-full bg-red-200" style={{ width: `${width}%` }} /> : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-xs">
          <span className="text-muted-foreground">Final churn score</span>
          <span className="text-sm font-semibold tabular-nums">{(record.churnProbability * 100).toFixed(1)}%</span>
        </div>
      </div>
    </div>
  );
}

export function PredictionDetailSheet({
  record,
  open,
  onOpenChange,
}: {
  record: PredictionRecord | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [copied, setCopied] = useState(false);

  if (!record) {
    return <Sheet open={open} onOpenChange={onOpenChange} />;
  }

  const DecisionIcon = decisionConfig[record.decision].icon;
  const actionBrief = [
    `Customer: ${record.customerId}`,
    `Industry: ${sectorLabel[record.sector]}`,
    `Risk: ${(record.churnProbability * 100).toFixed(1)}% (${record.riskTier})`,
    `Decision: ${record.decision}`,
    `Recommended action: ${record.recommendedAction}`,
    `Evidence: ${record.supportingEvidence.join("; ")}`,
  ].join("\n");

  async function copyActionBrief() {
    await navigator.clipboard.writeText(actionBrief);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle className="font-mono">{record.customerId}</SheetTitle>
          <SheetDescription>
            {sectorLabel[record.sector]} - Predicted {new Date(record.predictedAt).toLocaleString()}
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-5 px-4 pb-6">
          <div className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/30 px-4 py-3">
            <div>
              <p className="text-xs text-muted-foreground">Churn Probability</p>
              <p className="text-2xl font-semibold tabular-nums">{(record.churnProbability * 100).toFixed(1)}%</p>
            </div>
            <RiskTierBadge tier={record.riskTier} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border/60 bg-muted/30 px-3 py-2.5">
              <p className="text-xs text-muted-foreground">Coverage Intelligence</p>
              <p className="mt-1 text-lg font-semibold tabular-nums">{record.coverageScore}%</p>
            </div>
            <div className="rounded-lg border border-border/60 bg-muted/30 px-3 py-2.5">
              <p className="text-xs text-muted-foreground">Concept Confidence</p>
              <p className="mt-1 text-lg font-semibold tabular-nums">{record.conceptConfidenceScore}%</p>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Adaptive Routing</span>
            <RoutingTierBadge tier={record.routingTier} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Selected Model</span>
            <span className="text-sm font-medium">{record.selectedModel.replaceAll("_", " ")}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Decision Intelligence</span>
            <Badge variant="outline" className={cn("gap-1 font-medium", decisionConfig[record.decision].className)}>
              <DecisionIcon className="h-3.5 w-3.5" />
              {record.decision}
            </Badge>
          </div>

          <Separator />

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Business Explanation
            </p>
            <p className="text-sm leading-relaxed text-muted-foreground">{record.businessExplanation}</p>
          </div>

          <ContributionWaterfall record={record} />

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Signal Evidence
            </p>
            <div className="grid gap-2">
              {record.supportingEvidence.map((item, index) => (
                <div key={item} className="rounded-md border border-border/60 bg-background/75 p-3">
                  <div className="flex items-start gap-2">
                    {index % 2 === 0 ? <Signal className="mt-0.5 h-4 w-4 text-primary" /> : <Clock className="mt-0.5 h-4 w-4 text-primary" />}
                    <div>
                      <p className="text-sm font-medium">Evidence signal {index + 1}</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">{item}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {record.warnings.length > 0 ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/35">
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-amber-800 dark:text-amber-200">
                <AlertTriangle className="h-3.5 w-3.5" />
                Warnings
              </p>
              <ul className="flex flex-col gap-1">
                {record.warnings.map((w) => (
                  <li key={w} className="text-xs leading-relaxed text-amber-800/90 dark:text-amber-200/90">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <Separator />

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Recommended Action
            </p>
            <p className="text-sm leading-relaxed">{record.recommendedAction}</p>
            <Button type="button" variant="outline" size="sm" className="mt-3" onClick={copyActionBrief}>
              <ClipboardCheck className="mr-2 h-4 w-4" />
              {copied ? "Copied" : "Copy action brief"}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
