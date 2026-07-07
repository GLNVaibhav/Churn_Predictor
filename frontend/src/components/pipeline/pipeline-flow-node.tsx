"use client";

import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { StageStatusBadge } from "@/components/shared/status-badge";
import type { PipelineStage } from "@/lib/types";

export interface PipelineFlowNodeData {
  stage: PipelineStage;
  isSelected: boolean;
  isRunning: boolean;
  onSelect: (stage: PipelineStage) => void;
  [key: string]: unknown;
}

function PipelineFlowNodeInner({ data }: { data: PipelineFlowNodeData }) {
  const { stage, isSelected, isRunning, onSelect } = data;

  return (
    <motion.div
      layout
      animate={
        isRunning
          ? { scale: [1, 1.03, 1] }
          : { scale: 1 }
      }
      transition={isRunning ? { duration: 0.9, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }}
      onClick={() => onSelect(stage)}
      className={cn(
        "w-[220px] cursor-pointer rounded-xl border bg-card px-4 py-3 shadow-sm transition-colors",
        isSelected ? "border-primary/70 ring-1 ring-primary/40 shadow-md" : "border-border/60 hover:border-primary/40",
        isRunning && "border-blue-500/60 ring-1 ring-blue-500/30"
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-border !h-2 !w-2 !border-0" />
      <div className="flex items-center justify-between gap-2">
        <div
          className={cn(
            "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold tabular-nums",
            stage.status === "complete" && "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
            stage.status === "warning" && "border-amber-500/30 bg-amber-500/10 text-amber-400",
            stage.status === "failed" && "border-red-500/30 bg-red-500/10 text-red-400",
            (stage.status === "pending" || stage.status === "running") &&
              "border-border bg-muted text-muted-foreground"
          )}
        >
          {stage.order}
        </div>
        <p className="flex-1 truncate text-[13px] font-semibold leading-tight">{stage.shortLabel}</p>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <StageStatusBadge status={isRunning ? "running" : stage.status} className="text-[10px]" />
        <span className="text-[10px] tabular-nums text-muted-foreground">{stage.durationMs}ms</span>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-border !h-2 !w-2 !border-0" />
    </motion.div>
  );
}

export const PipelineFlowNode = memo(PipelineFlowNodeInner);
