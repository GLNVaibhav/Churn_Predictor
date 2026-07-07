"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  type Edge,
  type Node,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { PipelineStage } from "@/lib/types";
import { StageDetailPanel } from "@/components/pipeline/stage-detail-panel";
import { PipelineFlowNode, type PipelineFlowNodeData } from "@/components/pipeline/pipeline-flow-node";
import { Button } from "@/components/ui/button";
import { Play, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";

const nodeTypes: NodeTypes = {
  pipelineStage: PipelineFlowNode,
};

const COLUMN_WIDTH = 260;
const ROW_HEIGHT = 130;
const COLUMNS = 2;

function buildLayout(stages: PipelineStage[]) {
  return stages.map((stage, idx) => {
    const row = Math.floor(idx / COLUMNS);
    const col = idx % COLUMNS;
    const x = row % 2 === 0 ? col * COLUMN_WIDTH : (COLUMNS - 1 - col) * COLUMN_WIDTH;
    return { stage, x, y: row * ROW_HEIGHT };
  });
}

export function PipelineFlow({ stages }: { stages: PipelineStage[] }) {
  const [selectedStage, setSelectedStage] = useState<PipelineStage | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [runningStageId, setRunningStageId] = useState<string | null>(null);
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set(stages.map((s) => s.id)));
  const [isRunning, setIsRunning] = useState(false);
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const layout = useMemo(() => buildLayout(stages), [stages]);

  const handleSelect = useCallback((stage: PipelineStage) => {
    setSelectedStage(stage);
    setPanelOpen(true);
  }, []);

  const nodes: Node<PipelineFlowNodeData>[] = layout.map(({ stage, x, y }) => ({
    id: stage.id,
    type: "pipelineStage",
    position: { x, y },
    data: {
      stage: {
        ...stage,
        status: completedIds.has(stage.id) ? "complete" : "pending",
      },
      isSelected: selectedStage?.id === stage.id && panelOpen,
      isRunning: runningStageId === stage.id,
      onSelect: handleSelect,
    },
    draggable: false,
  }));

  const edges: Edge[] = stages.slice(0, -1).map((stage, idx) => {
    const next = stages[idx + 1];
    const active = completedIds.has(next.id) && completedIds.has(stage.id);
    return {
      id: `${stage.id}-${next.id}`,
      source: stage.id,
      target: next.id,
      animated: runningStageId === next.id,
      style: { stroke: active ? "var(--primary)" : "var(--border)", strokeWidth: 1.5, opacity: active ? 0.6 : 0.4 },
      markerEnd: { type: MarkerType.ArrowClosed, color: active ? "var(--primary)" : "var(--border)", width: 16, height: 16 },
    };
  });

  function clearTimeouts() {
    timeoutsRef.current.forEach((t) => clearTimeout(t));
    timeoutsRef.current = [];
  }

  function runAnalysis() {
    clearTimeouts();
    setIsRunning(true);
    setCompletedIds(new Set());
    setRunningStageId(null);

    stages.forEach((stage, idx) => {
      const startAt = idx * 550;
      const startTimeout = setTimeout(() => {
        setRunningStageId(stage.id);
      }, startAt);
      const finishTimeout = setTimeout(() => {
        setCompletedIds((prev) => new Set(prev).add(stage.id));
        if (idx === stages.length - 1) {
          setRunningStageId(null);
          setIsRunning(false);
        }
      }, startAt + 500);
      timeoutsRef.current.push(startTimeout, finishTimeout);
    });
  }

  function resetRun() {
    clearTimeouts();
    setIsRunning(false);
    setRunningStageId(null);
    setCompletedIds(new Set(stages.map((s) => s.id)));
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          Drag to pan, scroll to zoom, click any stage for its execution detail.
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={resetRun} disabled={isRunning}>
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </Button>
          <Button size="sm" onClick={runAnalysis} disabled={isRunning}>
            <Play className={cn("h-3.5 w-3.5", isRunning && "animate-pulse")} />
            {isRunning ? "Running…" : "Run Analysis"}
          </Button>
        </div>
      </div>
      <div className="h-[620px] w-full overflow-hidden rounded-lg border border-border/60 bg-muted/10">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          minZoom={0.5}
          maxZoom={1.5}
          proOptions={{ hideAttribution: true }}
          nodesConnectable={false}
          elementsSelectable={false}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} className="opacity-40" />
          <Controls showInteractive={false} className="!bottom-3 !left-3" />
        </ReactFlow>
      </div>
      <StageDetailPanel stage={selectedStage} open={panelOpen} onOpenChange={setPanelOpen} />
    </div>
  );
}
