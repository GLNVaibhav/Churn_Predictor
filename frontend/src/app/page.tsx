import Link from "next/link";
import { ArrowRight, Braces, LockKeyhole } from "lucide-react";
import { Button } from "@/components/ui/button";
import { UcifLogo } from "@/components/brand/ucif-logo";
import { Reveal } from "@/components/motion/reveal";

const platformUrl = "/dashboard";
const githubUrl = "https://github.com/GLNVaibhav/Churn_Predictor";

const customers = [
  ["HDFC-1042", "Banking", "82.1%", "At Risk", "Low engagement"],
  ["HDFC-1178", "Banking", "71.4%", "Escalate", "Support escalation"],
  ["HDFC-1236", "Banking", "18.9%", "Stable", "Healthy activity"],
];

function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-border/80 bg-background/92 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5">
        <Link href="/" aria-label="UCIF home">
          <UcifLogo sublabel="Churn Intelligence" />
        </Link>
        <nav className="hidden items-center gap-6 text-sm font-medium text-muted-foreground md:flex">
          <a href="#product" className="hover:text-foreground">Product</a>
          <a href="#data" className="hover:text-foreground">Data preview</a>
          <a href="#start" className="hover:text-foreground">Start</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/signin">
            <Button variant="outline" size="sm">
              <LockKeyhole className="mr-2 h-4 w-4" />
              Sign in
            </Button>
          </Link>
          <Link href={platformUrl}>
            <Button size="sm">
              Open app
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>
    </header>
  );
}

function WorkspacePreview() {
  return (
    <div className="premium-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-border bg-muted/25 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/30" />
          <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/30" />
          <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/30" />
        </div>
        <span className="text-xs font-medium text-muted-foreground">Retention workspace</span>
      </div>
      <div className="grid min-h-[420px] lg:grid-cols-[180px_1fr]">
        <div className="hidden border-r border-border bg-sidebar p-4 text-sidebar-foreground lg:block">
          <UcifLogo tone="sidebar" sublabel="Intelligence" markClassName="h-8 w-8" />
          <div className="mt-6 space-y-1 text-xs font-medium">
            {["Home", "Workspace", "Analyses", "Reports"].map((item, index) => (
              <div key={item} className={index === 2 ? "rounded-md bg-sidebar-foreground px-3 py-2 text-sidebar" : "px-3 py-2 text-sidebar-foreground/58"}>
                {item}
              </div>
            ))}
          </div>
        </div>
        <div className="bg-card p-5">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-primary">Banking run</p>
              <h3 className="mt-1 text-xl font-semibold tracking-tight">Churn risk analysis</h3>
            </div>
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">
              Complete
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {[
              ["550", "Rows"],
              ["394", "At risk"],
              ["69.5%", "Avg risk"],
            ].map(([value, label]) => (
              <div key={label} className="rounded-md border border-border bg-background p-3">
                <p className="text-xl font-semibold tabular-nums">{value}</p>
                <p className="mt-1 text-[11px] font-medium text-muted-foreground">{label}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-md border border-border bg-background p-4">
            <p className="mb-3 text-sm font-semibold">Top retention drivers</p>
            {[
              ["Low engagement", "82%", "Impact score 91"],
              ["Declining account activity", "71%", "Impact score 78"],
              ["Support escalation", "58%", "Impact score 66"],
            ].map(([label, value, impact]) => (
              <div key={label} className="mb-3 last:mb-0">
                <div className="mb-1 flex justify-between gap-3 text-xs">
                  <span className="font-medium">{label}</span>
                  <span className="text-muted-foreground">{value} - {impact}</span>
                </div>
                <div className="h-2 rounded-full bg-muted">
                  <div className="h-2 rounded-full bg-red-200" style={{ width: value }} />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-md border border-border bg-muted/20 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">ABIL context</p>
            <p className="mt-1 text-sm font-medium">25 business signals applied to decision support.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function BentoGrid() {
  return (
    <section id="product" className="border-t border-border bg-background py-16">
      <div className="mx-auto max-w-7xl px-5">
        <Reveal className="mb-8 max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary">Product</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">One workspace. Churn risk, evidence, and action.</h2>
        </Reveal>
        <div className="grid gap-4 lg:grid-cols-6">
          <Reveal className="lg:col-span-3 lg:row-span-2">
            <WorkspacePreview />
          </Reveal>
          <Reveal delay={0.05} className="premium-panel p-6 lg:col-span-3">
            <p className="text-sm font-semibold">Analysis workflow</p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              {[
                ["CSV", "Upload customer records"],
                ["Context", "Inject ABIL signals"],
                ["Output", "Explain risk and actions"],
              ].map(([label, body]) => (
                <div key={label} className="border-l border-border pl-4">
                  <p className="text-sm font-semibold">{label}</p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">{body}</p>
                </div>
              ))}
            </div>
          </Reveal>
          <Reveal delay={0.08} className="premium-panel p-6 lg:col-span-2">
            <p className="text-sm font-semibold">Domain intelligence</p>
            <div className="mt-4 grid gap-3">
              {[
                ["Telecom", "Contract expiry, recharge decay, service complaints"],
                ["Banking", "Balance drop, fee sensitivity, dormant accounts"],
                ["E-commerce", "Purchase gaps, return friction, discount dependence"],
                ["Healthcare", "Appointment gaps, plan disengagement, access delays"],
              ].map(([industry, driver]) => (
                <div key={industry} className="rounded-md border border-border bg-background px-3 py-2">
                  <p className="text-xs font-semibold">{industry}</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">{driver}</p>
                </div>
              ))}
            </div>
          </Reveal>
          <Reveal delay={0.11} className="premium-panel p-6 lg:col-span-2">
            <p className="text-sm font-semibold">Manual routing</p>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Auto-detect sectors when useful. Override manually when the business domain is known.
            </p>
          </Reveal>
          <Reveal delay={0.14} className="premium-panel p-6 lg:col-span-2">
            <div className="flex items-center gap-2">
              <Braces className="h-4 w-4 text-primary" />
              <p className="text-sm font-semibold">Humanized context</p>
            </div>
            <pre className="mt-4 overflow-hidden rounded-md border border-border bg-background p-3 text-xs text-muted-foreground">
{`{
  "signal": "Premium retention",
  "severity": "HIGH"
}`}
            </pre>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function DataPreview() {
  return (
    <section id="data" className="border-t border-border py-16">
      <div className="mx-auto max-w-7xl px-5">
        <Reveal className="mb-8 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">Data UX</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">Dense, readable, and ready to drill down.</h2>
          </div>
          <p className="max-w-md text-sm leading-6 text-muted-foreground">
            Customer rows stay scannable, with risk states and evidence available through the workspace drawer.
          </p>
        </Reveal>
        <Reveal className="premium-panel overflow-x-auto">
          <div className="grid min-w-[720px] grid-cols-[1fr_120px_110px_1fr] border-b border-border bg-muted/30 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <span>Customer</span>
            <span>Industry</span>
            <span className="text-right">Risk</span>
            <span className="text-right">Driver</span>
          </div>
          {customers.map(([id, industry, risk, state, driver]) => (
            <div key={id} className="grid min-w-[720px] grid-cols-[1fr_120px_110px_1fr] items-center border-b border-border/60 px-4 py-3 text-sm last:border-b-0">
              <span className="font-mono text-xs">{id}</span>
              <span>{industry}</span>
              <span className="text-right font-semibold tabular-nums">{risk}</span>
              <span className="text-right">
                <span className={state === "Stable" ? "rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800" : "rounded-full border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-medium text-red-800"}>
                  {state}
                </span>
                <span className="ml-2 text-xs text-muted-foreground">{driver}</span>
              </span>
            </div>
          ))}
        </Reveal>
      </div>
    </section>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <Header />
      <section className="relative overflow-hidden">
        <div className="hero-grid absolute inset-0" />
        <div className="relative mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl items-center gap-10 px-5 py-16 lg:grid-cols-[0.88fr_1.12fr]">
          <Reveal>
            <p className="inline-flex rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-primary">
              Churn Intelligence Workspace
            </p>
            <h1 className="mt-5 max-w-4xl text-4xl font-semibold tracking-tight md:text-6xl">
              Predict churn. Explain risk. Prioritize retention.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground md:text-lg">
              UCIF turns raw customer datasets into a focused workspace for scoring churn, reading semantic evidence,
              comparing execution output, and deciding the next retention action.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link href={platformUrl}>
                <Button size="lg">
                  Open app
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Link href={githubUrl}>
                <Button variant="outline" size="lg">View source</Button>
              </Link>
            </div>
          </Reveal>
          <Reveal delay={0.08}>
            <WorkspacePreview />
          </Reveal>
        </div>
      </section>
      <BentoGrid />
      <DataPreview />
      <section id="start" className="border-t border-border bg-background py-12">
        <Reveal className="mx-auto flex max-w-7xl flex-col gap-5 px-5 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Run a customer analysis in UCIF.</h2>
            <p className="mt-2 text-sm text-muted-foreground">Upload data, choose the domain, add context, and open the workspace.</p>
          </div>
          <Link href={platformUrl}>
            <Button size="lg">
              Open app
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </Reveal>
      </section>
      <footer className="border-t border-border bg-background py-7">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 text-sm text-muted-foreground md:flex-row md:items-center md:justify-between">
          <p>Universal Churn Intelligence Framework</p>
          <div className="flex flex-wrap gap-4">
            <Link href={platformUrl} className="hover:text-foreground">Platform</Link>
            <Link href="/signin" className="hover:text-foreground">Sign in</Link>
            <Link href={githubUrl} className="hover:text-foreground">GitHub</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
