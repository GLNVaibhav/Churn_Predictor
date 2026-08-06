"use client";

import { createContext, useContext } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type AuthUser = { userId: string; email: string; name: string; role?: "admin" | "member" };
type AuthContextValue = {
  configured: boolean;
  connected: boolean;
  error: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  login: (input: { email: string; password: string }) => Promise<void>;
  register: (input: { email: string; password: string; name: string }) => Promise<void>;
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
  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => authRequest<{ configured: boolean; connected: boolean; error: string | null; user: AuthUser | null }>("/api/auth/me"),
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
        user: me.data?.user || null,
        isLoading: me.isLoading,
        login: async (input) => { await loginMutation.mutateAsync(input); },
        register: async (input) => { await registerMutation.mutateAsync(input); },
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
