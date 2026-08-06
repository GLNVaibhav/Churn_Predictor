"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/context/auth-context";
import { ArrowLeft, LockKeyhole, ShieldCheck, UserPlus } from "lucide-react";
import Link from "next/link";
import { UcifLogo } from "@/components/brand/ucif-logo";

export default function SignInPage() {
  const router = useRouter();
  const auth = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      if (mode === "login") await auth.login({ email, password });
      else await auth.register({ email, password, name });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <PageShell className="min-h-screen items-center justify-center px-5 py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-lg border border-border bg-card ring-1 ring-black/5 lg:grid-cols-[1fr_420px]">
        <div className="hidden border-r border-border bg-sidebar p-8 text-sidebar-foreground lg:block">
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium text-sidebar-foreground/70 hover:text-sidebar-foreground">
            <ArrowLeft className="h-4 w-4" />
            Back to UCIF
          </Link>
          <div className="mt-16">
            <UcifLogo tone="sidebar" showWordmark={false} markClassName="mb-6 h-11 w-11" />
            <h1 className="max-w-sm text-3xl font-semibold tracking-tight">Secure access for retention intelligence teams.</h1>
            <p className="mt-4 max-w-sm text-sm leading-6 text-sidebar-foreground/58">
              Sign in to run analyses, restore workspace output, and keep reports connected to the right account.
            </p>
          </div>
          <div className="mt-14 grid gap-3">
            {["Secure workspace access", "Protected session cookie", "Customer-ready workspace"].map((item) => (
              <div key={item} className="flex items-center gap-3 rounded-md border border-sidebar-border bg-white/[0.06] px-3 py-2 text-sm">
                <ShieldCheck className="h-4 w-4 text-emerald-300" />
                {item}
              </div>
            ))}
          </div>
        </div>
        <div className="w-full p-5 sm:p-8">
          <Link href="/" className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground lg:hidden">
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
        <SectionCard
          title={mode === "login" ? "Sign in to UCIF" : "Create workspace account"}
          description="Access the customer retention workspace."
          className="border-0 shadow-none ring-0"
        >
          <div className="mb-4 flex items-center justify-between rounded-md border border-border bg-muted/20 px-3 py-2">
            <span className="text-xs font-medium text-muted-foreground">Authentication</span>
            <Badge variant="outline">{auth.connected ? "Connected" : "Database not connected"}</Badge>
          </div>
          {auth.error ? (
            <p className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
              {auth.error}
            </p>
          ) : null}

          <form className="space-y-4" onSubmit={submit}>
            {mode === "register" ? (
              <div className="space-y-1.5">
                <Label htmlFor="name">Name</Label>
                <Input id="name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Workspace owner" />
              </div>
            ) : null}
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 8 characters" required />
            </div>
            {error ? <p className="text-xs text-destructive">{error}</p> : null}
            <Button type="submit" className="w-full" disabled={pending || !auth.connected}>
              {mode === "login" ? <LockKeyhole className="mr-2 h-4 w-4" /> : <UserPlus className="mr-2 h-4 w-4" />}
              {pending ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <button
            type="button"
            className="mt-4 w-full text-center text-xs font-medium text-primary hover:underline"
            onClick={() => {
              setMode((current) => (current === "login" ? "register" : "login"));
              setError(null);
            }}
          >
            {mode === "login" ? "Create a new workspace account" : "Already have an account? Sign in"}
          </button>
        </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}
