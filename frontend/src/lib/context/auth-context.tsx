"use client";

import { createContext, useContext } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type AuthUser = {
  userId: string;
  email: string;
  name: string;
  role?: "admin" | "member";
  accountType?: "demo";
  roleLabel?: "Research Demonstrator";
};
type AuthContextValue = {
  configured: boolean;
  connected: boolean;
  error: string | null;
  demoEnabled: boolean;
  demoPending: boolean;
  user: AuthUser | null;
  isLoading: boolean;
  login: (input: { email: string; password: string }) => Promise<void>;
  register: (input: { email: string; password: string; name: string }) => Promise<void>;
  enterDemo: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function authRequest<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Authentication request failed.");
  return data;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const demoStatus = useQuery({
    queryKey: ["auth", "demo-status"],
    queryFn: () => authRequest<{ enabled: boolean }>("/api/auth/demo/status"),
    retry: 0,
  });
  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => authRequest<{ configured: boolean; connected: boolean; error: string | null; demoEnabled: boolean; user: AuthUser | null }>("/api/auth/me"),
    retry: 0,
  });
  const loginMutation = useMutation({
    mutationFn: (input: { email: string; password: string }) => authRequest("/api/auth/login", input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth", "me"] }),
  });
  const registerMutation = useMutation({
    mutationFn: (input: { email: string; password: string; name: string }) => authRequest("/api/auth/register", input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth", "me"] }),
  });
  const demoMutation = useMutation({
    mutationFn: () => authRequest<{ user: AuthUser }>("/api/auth/demo", {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth", "me"] }),
  });
  const logoutMutation = useMutation({
    mutationFn: () => authRequest("/api/auth/logout", {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["auth", "me"] }),
  });

  return (
    <AuthContext.Provider
      value={{
        configured: Boolean(me.data?.configured),
        connected: Boolean(me.data?.connected),
        error: me.data?.error || null,
        demoEnabled: Boolean(demoStatus.data?.enabled),
        demoPending: demoMutation.isPending,
        user: me.data?.user || null,
        isLoading: me.isLoading,
        login: async (input) => { await loginMutation.mutateAsync(input); },
        register: async (input) => { await registerMutation.mutateAsync(input); },
        enterDemo: async () => { await demoMutation.mutateAsync(); },
        logout: async () => { await logoutMutation.mutateAsync(); },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
