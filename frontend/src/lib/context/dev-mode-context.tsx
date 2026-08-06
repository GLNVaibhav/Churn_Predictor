"use client";

import { createContext, useContext } from "react";

type DevModeContextValue = {
  developerMode: boolean;
  setDeveloperMode: (value: boolean) => void;
  toggleDeveloperMode: () => void;
};

const DevModeContext = createContext<DevModeContextValue | null>(null);

export function DevModeProvider({ children }: { children: React.ReactNode }) {
  return (
    <DevModeContext.Provider value={{ developerMode: false, setDeveloperMode: () => {}, toggleDeveloperMode: () => {} }}>
      {children}
    </DevModeContext.Provider>
  );
}

export function useDevMode() {
  const ctx = useContext(DevModeContext);
  if (!ctx) throw new Error("useDevMode must be used within a DevModeProvider");
  return ctx;
}
