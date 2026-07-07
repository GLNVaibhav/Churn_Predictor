"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type ExecutionContextState = {
  uploadId: string | null;
  executionId: string | null;
  filename: string | null;
  sector: string | null;
  status: string | null;
};

type ExecutionContextValue = ExecutionContextState & {
  setExecutionContext: (next: Partial<ExecutionContextState>) => void;
  clearExecutionContext: () => void;
};

const STORAGE_KEY = "ucif:execution-context";

const emptyState: ExecutionContextState = {
  uploadId: null,
  executionId: null,
  filename: null,
  sector: null,
  status: null,
};

const ExecutionContext = createContext<ExecutionContextValue | null>(null);

export function ExecutionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<ExecutionContextState>(emptyState);

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      setState({ ...emptyState, ...JSON.parse(raw) });
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const value = useMemo<ExecutionContextValue>(() => {
    function persist(next: ExecutionContextState) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    }

    return {
      ...state,
      setExecutionContext: (next) => setState((prev) => persist({ ...prev, ...next })),
      clearExecutionContext: () => setState(persist(emptyState)),
    };
  }, [state]);

  return <ExecutionContext.Provider value={value}>{children}</ExecutionContext.Provider>;
}

export function useExecutionContext() {
  const ctx = useContext(ExecutionContext);
  if (!ctx) throw new Error("useExecutionContext must be used within ExecutionProvider");
  return ctx;
}
