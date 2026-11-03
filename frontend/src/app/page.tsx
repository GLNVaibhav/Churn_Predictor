import Link from "next/link";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { Button } from "@/components/ui/button";
import { UcifLogo } from "@/components/brand/ucif-logo";
import { DataSourceBadge } from "@/components/shared/data-source-badge";
import { LandingHero } from "@/components/landing/landing-hero";
import { FeatureShowcase } from "@/components/landing/feature-showcase";
import { EditorialInterlude, PinnedWorkflowStory } from "@/components/landing/workflow-story";

const exampleRows = [
  ["Sample-1042", "Banking", "82.1%", "At Risk"],
  ["Sample-1178", "Banking", "71.4%", "Escalate"],
  ["Sample-1236", "Banking", "18.9%", "Stable"],
];

function Header() {
  return (
    <header className="landing-header sticky top-0 z-50 border-b border-white/[.08]">
      <div className="mx-auto flex h-[4.25rem] max-w-7xl items-center justify-between gap-4 px-5 sm:px-8">
        <Link href="/" aria-label="UCIF home"><UcifLogo tone="inverse" sublabel="Churn Intelligence" /></Link>
        <nav aria-label="Landing page navigation" className="hidden items-center gap-7 text-xs font-medium text-slate-400 md:flex">
          <a href="#product" className="transition-colors hover:text-white">Platform workflow</a>
          <a href="#data" className="transition-colors hover:text-white">Data preview</a>
          <a href="#start" className="transition-colors hover:text-white">Get started</a>
        </nav>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" size="sm" className="hidden border-white/15 bg-white/[.03] text-slate-200 hover:bg-white/10 hover:text-white sm:inline-flex" render={<Link href="/signin" />}>
            <LockKeyhole className="mr-1.5 h-3.5 w-3.5" /> Sign in
          </Button>
          <Button size="sm" className="bg-white text-black hover:bg-neutral-200" render={<Link href="/dashboard" />}>
            Open app <ArrowRight className="ml-1 h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </header>
  );
}

function DataPreview() {
  return (
    <section id="data" className="border-t border-border/70 bg-muted/20 py-16 sm:py-20">
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <div className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[.18em] text-primary">Output presentation</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-.03em] sm:text-3xl">Readable customer-level results.</h2>
          </div>
          <div className="max-w-md space-y-2">
            <DataSourceBadge kind="demonstration" label="Illustrative sample values" />
            <p className="text-xs leading-5 text-muted-foreground">This interface preview is not a UCIF execution. Actual result fields depend on the uploaded dataset and service response.</p>
          </div>
        </div>
        <div className="overflow-x-auto rounded-2xl border border-border/80 bg-card shadow-[var(--shadow-card)]">
          <div className="grid min-w-[660px] grid-cols-[1fr_130px_130px_130px] border-b border-border bg-muted/40 px-5 py-3 text-[10px] font-semibold uppercase tracking-[.14em] text-muted-foreground">
            <span>Example customer</span><span>Sector</span><span className="text-right">Sample risk</span><span className="text-right">Example state</span>
          </div>
          {exampleRows.map(([id, sector, risk, status]) => (
            <div key={id} className="grid min-w-[660px] grid-cols-[1fr_130px_130px_130px] items-center border-b border-border/60 px-5 py-4 text-sm last:border-0">
              <span className="font-mono text-xs">{id}</span><span className="text-muted-foreground">{sector}</span><span className="text-right font-medium tabular-nums">{risk}</span>
              <span className="text-right"><span className="rounded-full border border-border bg-muted px-2.5 py-1 text-[10px] font-medium">{status}</span></span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <Header />
      <LandingHero />
      <EditorialInterlude />
      <PinnedWorkflowStory />
      <FeatureShowcase />
      <DataPreview />
      <section id="start" className="relative overflow-hidden border-t border-neutral-200 bg-[#EDEDED] py-16 text-[#111111] sm:py-20">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 sm:px-8 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[.2em] text-neutral-500">Start with your dataset</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-.03em]">Bring a customer dataset into UCIF.</h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-neutral-600">Upload a file, confirm its sector, and review the results returned for the analysis.</p>
          </div>
          <Button size="lg" className="h-11 w-fit rounded-lg px-5" render={<Link href="/upload" />}>Start an analysis <ArrowRight className="ml-1 h-4 w-4" /></Button>
        </div>
      </section>
      <footer className="border-t border-neutral-200 bg-[#EDEDED] py-6 text-[#111111]">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 text-xs text-neutral-500 sm:px-8 md:flex-row md:items-center md:justify-between">
          <p>Universal Churn Intelligence Framework</p>
          <div className="flex flex-wrap gap-5">
            <Link href="/dashboard" className="hover:text-black">Platform</Link>
            <Link href="/signin" className="hover:text-black">Sign in</Link>
            <a href="https://github.com/GLNVaibhav/Churn_Predictor" className="hover:text-black">Source</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
