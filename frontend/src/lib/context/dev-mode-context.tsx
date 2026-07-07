"use client";

import { createContext, useContext, useEffect, useState } from "react";

type DevModeContextValue = {
  developerMode: boolean;
  setDeveloperMode: (value: boolean) => void;
  toggleDeveloperMode: () => void;
};

const DevModeContext = createContext<DevModeContextValue | null>(null);

const STORAGE_KEY = "universal-churn:developer-mode";

export function DevModeProvider({ children }: { children: React.ReactNode }) {
  const [developerMode, setDeveloperModeState] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "true") setDeveloperModeState(true);
    setHydrated(true);
  }, []);

  function setDeveloperMode(value: boolean) {
    setDeveloperModeState(value);
    window.localStorage.setItem(STORAGE_KEY, String(value));
  }

  function toggleDeveloperMode() {
    setDeveloperMode(!developerMode);
  }

  return (
    <DevModeContext.Provider value={{ developerMode: hydrated ? developerMode : false, setDeveloperMode, toggleDeveloperMode }}>
      {children}
    </DevModeContext.Provider>
  );
}

export function useDevMode() {
  const ctx = useContext(DevModeContext);
  if (!ctx) throw new Error("useDevMode must be used within a DevModeProvider");
  return ctx;
}
