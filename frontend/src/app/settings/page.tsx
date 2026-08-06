"use client";

import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Bell, Building2, Database, LockKeyhole, Settings2, UserRound } from "lucide-react";
import { useAuth } from "@/lib/context/auth-context";

export default function SettingsPage() {
  const auth = useAuth();

  return (
    <PageShell>
      <div className="premium-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">Settings</p>
            <h2 className="mt-2 max-w-3xl text-2xl font-semibold tracking-tight">
              Configure the workspace without exposing product internals.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Manage account identity, analysis preferences, notifications, storage status, and service availability.
            </p>
          </div>
          <Settings2 className="h-6 w-6 text-primary" />
        </div>
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <SectionCard title="Workspace Profile" description="Customer-facing workspace identity">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="workspace-name">Workspace name</Label>
                <Input id="workspace-name" defaultValue="UCIF Retention Workspace" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="company">Company</Label>
                <Input id="company" defaultValue="Universal Churn Intelligence" />
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Analysis Preferences" description="Defaults used when a new analysis starts">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-md border border-border bg-muted/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">Manual industry confirmation</p>
                    <p className="mt-1 text-xs text-muted-foreground">Ask users to confirm the industry before execution.</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </div>
              <div className="rounded-md border border-border bg-muted/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">Business context prompts</p>
                    <p className="mt-1 text-xs text-muted-foreground">Show optional market/context input during analysis.</p>
                  </div>
                  <Switch defaultChecked />
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Notifications" description="Operational alerts for analysis completion and risk changes">
            <div className="space-y-3">
              {["Analysis completed", "High-risk segment detected", "Report ready"].map((label) => (
                <div key={label} className="flex items-center justify-between rounded-md border border-border bg-muted/20 px-3 py-2">
                  <div className="flex items-center gap-2">
                    <Bell className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium">{label}</span>
                  </div>
                  <Switch defaultChecked />
                </div>
              ))}
            </div>
          </SectionCard>
        </div>

        <div className="space-y-5">
          <SectionCard title="Account" description="Signed-in workspace identity">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
                <UserRound className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-semibold">{auth.user?.name || "Workspace Owner"}</p>
                <p className="text-xs text-muted-foreground">{auth.user?.email || "No account signed in"}</p>
              </div>
            </div>
            <Link href="/signin">
              <Button variant="outline" size="sm" className="mt-4 w-full">{auth.user ? "Switch account" : "Sign in"}</Button>
            </Link>
          </SectionCard>

          <SectionCard title="Security" description="Customer access controls">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2"><LockKeyhole className="h-4 w-4 text-primary" />Authentication</span>
                <Badge variant="outline">{auth.connected ? "Connected" : "Not connected"}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2"><Building2 className="h-4 w-4 text-primary" />Team access</span>
                <Badge variant="outline">Next</Badge>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Data Storage" description="Persistence for users, uploads, analyses, and reports">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2"><Database className="h-4 w-4 text-primary" />Database</span>
              <Badge variant="outline">{auth.connected ? "Connected" : "Not connected"}</Badge>
            </div>
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              Workspace accounts and session state are connected for the deployed product experience.
            </p>
            {auth.error ? <p className="mt-2 text-xs text-amber-700">{auth.error}</p> : null}
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}
