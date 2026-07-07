"use client";

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
import { AlertTriangle, CheckCircle2, Code2, XCircle } from "lucide-react";
import type { PredictionRecord } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useDevMode } from "@/lib/context/dev-mode-context";

const sectorLabel: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  healthcare: "Healthcare",
  ecommerce: "E-commerce",
};

const decisionConfig: Record<PredictionRecord["decision"], { icon: typeof CheckCircle2; className: string }> = {
  Approved: { icon: CheckCircle2, className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" },
  Escalate: { icon: AlertTriangle, className: "border-amber-500/30 bg-amber-500/10 text-amber-400" },
  Refused: { icon: XCircle, className: "border-red-500/30 bg-red-500/10 text-red-400" },
};

export function PredictionDetailSheet({
  record,
  open,
  onOpenChange,
}: {
  record: PredictionRecord | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { developerMode } = useDevMode();

  if (!record) {
    return <Sheet open={open} onOpenChange={onOpenChange} />;
  }

  const DecisionIcon = decisionConfig[record.decision].icon;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="font-mono">{record.customerId}</SheetTitle>
          <SheetDescription>
            {sectorLabel[record.sector]} · Predicted {new Date(record.predictedAt).toLocaleString()}
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

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Supporting Evidence
            </p>
            <ul className="flex flex-col gap-1.5">
              {record.supportingEvidence.map((item) => (
                <li key={item} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-muted-foreground" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {record.warnings.length > 0 ? (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-amber-400">
                <AlertTriangle className="h-3.5 w-3.5" />
                Warnings
              </p>
              <ul className="flex flex-col gap-1">
                {record.warnings.map((w) => (
                  <li key={w} className="text-xs leading-relaxed text-amber-400/90">
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
          </div>

          {developerMode ? (
            <>
              <Separator />
              <div>
                <div className="mb-2 flex items-center gap-1.5">
                  <Code2 className="h-3.5 w-3.5 text-muted-foreground" />
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Raw prediction record
                  </p>
                </div>
                <pre className="overflow-x-auto rounded-lg border border-border/60 bg-muted/40 p-3 text-[11px] leading-relaxed">
                  {JSON.stringify(record, null, 2)}
                </pre>
              </div>
            </>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
