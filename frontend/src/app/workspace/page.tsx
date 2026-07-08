"use client";

import { Suspense } from "react";
import { LoadingState } from "@/components/shared/query-states";
import WorkspacePageInner from "./workspace-inner";

export default function WorkspacePage() {
  return (
    <Suspense fallback={<LoadingState label="Loading workspace..." />}>
      <WorkspacePageInner />
    </Suspense>
  );
}
