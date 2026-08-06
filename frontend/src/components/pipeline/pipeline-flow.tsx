"use client";

import { useCallback, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { PipelineStage } from "@/lib/types";
import { StageDetailPanel } from "@/components/pipeline/stage-detail-panel";
import { PipelineFlowNode, type PipelineFlowNodeData } from "@/components/pipeline/pipeline-flow-node";

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
      stage,
      isSelected: selectedStage?.id === stage.id && panelOpen,
      isRunning: stage.status === "running",
      onSelect: handleSelect,
    },
    draggable: false,
  }));

  const edges: Edge[] = stages.slice(0, -1).map((stage, idx) => {
    const next = stages[idx + 1];
    const active = stage.status === "complete" && (next.status === "complete" || next.status === "running");
    return {
      id: `${stage.id}-${next.id}`,
      source: stage.id,
      target: next.id,
      animated: next.status === "running",
      style: { stroke: active ? "var(--primary)" : "var(--border)", strokeWidth: 1.5, opacity: active ? 0.6 : 0.4 },
      markerEnd: { type: MarkerType.ArrowClosed, color: active ? "var(--primary)" : "var(--border)", width: 16, height: 16 },
    };
  });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          Follow the analysis from upload through readiness checks, risk scoring, and decision support.
        </p>
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
