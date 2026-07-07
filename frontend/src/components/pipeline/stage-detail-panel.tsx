"use client";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { StageStatusBadge } from "@/components/shared/status-badge";
import type { PipelineStage } from "@/lib/types";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { useDevMode } from "@/lib/context/dev-mode-context";
import { Code2 } from "lucide-react";

interface StageDetailPanelProps {
  stage: PipelineStage | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function StageDetailPanel({ stage, open, onOpenChange }: StageDetailPanelProps) {
  const { developerMode } = useDevMode();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md overflow-y-auto">
        {stage ? (
          <>
            <SheetHeader>
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-xs font-semibold tabular-nums">
                  {stage.order}
                </span>
                <SheetTitle>{stage.name}</SheetTitle>
              </div>
              <SheetDescription>{stage.description}</SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-5 px-4 pb-6">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Stage status</span>
                <StageStatusBadge status={stage.status} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Execution time</span>
                <span className="text-sm font-medium tabular-nums">{stage.durationMs} ms</span>
              </div>
              <Separator />
              <div>
                <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Stage metrics
                </p>
                <div className="grid grid-cols-1 gap-3">
                  {stage.metrics.map((m) => (
                    <div
                      key={m.label}
                      className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/30 px-3 py-2"
                    >
                      <span className="text-sm text-muted-foreground">{m.label}</span>
                      <span className="text-sm font-medium tabular-nums">{m.value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <Separator />
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  How this stage works
                </p>
                <p className="text-sm leading-relaxed text-muted-foreground">{stage.detail}</p>
              </div>

              {developerMode ? (
                <>
                  <Separator />
                  <div>
                    <div className="mb-2 flex items-center gap-1.5">
                      <Code2 className="h-3.5 w-3.5 text-muted-foreground" />
                      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Developer detail
                      </p>
                    </div>
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/30 px-3 py-2">
                        <span className="text-sm text-muted-foreground">Backend module</span>
                        <Badge variant="outline" className="font-mono text-[11px]">
                          {stage.backendModule}
                        </Badge>
                      </div>
                      <div className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/30 px-3 py-2">
                        <span className="text-sm text-muted-foreground">Future endpoint</span>
                        <Badge variant="outline" className="font-mono text-[11px]">
                          {stage.futureEndpoint}
                        </Badge>
                      </div>
                      <div>
                        <p className="mb-1.5 text-xs font-medium text-muted-foreground">Input sample</p>
                        <pre className="overflow-x-auto rounded-lg border border-border/60 bg-muted/40 p-3 text-[11px] leading-relaxed">
                          {stage.inputSample}
                        </pre>
                      </div>
                      <div>
                        <p className="mb-1.5 text-xs font-medium text-muted-foreground">Output sample</p>
                        <pre className="overflow-x-auto rounded-lg border border-border/60 bg-muted/40 p-3 text-[11px] leading-relaxed">
                          {stage.outputSample}
                        </pre>
                      </div>
                      <div>
                        <p className="mb-1.5 text-xs font-medium text-muted-foreground">Notes</p>
                        <p className="text-sm leading-relaxed text-muted-foreground">{stage.notes}</p>
                      </div>
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
