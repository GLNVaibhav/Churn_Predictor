"use client";

const STORAGE_KEY = "ucif:expired-executions";

function readExpired() {
  if (typeof window === "undefined") return new Set<string>();
  try {
    return new Set<string>(JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || "[]"));
  } catch {
    return new Set<string>();
  }
}

export function rememberExpiredExecution(id: string | null | undefined) {
  if (!id || typeof window === "undefined") return;
  const expired = readExpired();
  expired.add(id);
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...expired]));
}

export function isExpiredExecution(id: string | null | undefined) {
  if (!id) return false;
  return readExpired().has(id);
}
