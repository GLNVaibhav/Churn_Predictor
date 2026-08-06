"use client";

import { useMemo, useState } from "react";
import { PageShell } from "@/components/layout/page-shell";
import { ErrorBanner, LoadingState } from "@/components/shared/query-states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Reveal } from "@/components/motion/reveal";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { sectorLabel } from "@/lib/constants/sectors";
import { cn } from "@/lib/utils";
import { BookOpen, Braces, Check, CheckCircle2, Clipboard, Compass, FileText, Route, Search, ShieldCheck, TriangleAlert } from "lucide-react";

type FrameworkInfo = {
  framework_version: string;
  supported_sectors: string[];
  available_modules: string[];
};

const docs = [
  {
    id: "overview",
    group: "Framework",
    title: "Framework Overview",
    eyebrow: "Start here",
    icon: BookOpen,
    body:
      "UCIF turns customer datasets into churn risk scores, semantic evidence, comparison views, and decision support. Analysts upload a dataset, confirm the domain, inspect the analysis output, and export reports tied to the selected run.",
    bullets: [
      "A run is the execution event created from an uploaded CSV.",
      "An analysis is the output: predictions, evidence, comparison, and decisions.",
      "The workspace is the app area where an analysis is explored.",
    ],
  },
  {
    id: "abil",
    group: "Evidence",
    title: "ABIL Contexts",
    eyebrow: "Business signals",
    icon: Braces,
    body:
      "ABIL contexts enrich model output with business facts that are not present in the dataset. Use them for retention objectives, market events, campaign changes, risk thresholds, and operational constraints.",
    bullets: [
      "Keep context concise and event-oriented.",
      "Use severity and category fields when a signal affects priority.",
      "Raw payloads stay behind disclosure surfaces in the product UI.",
    ],
    warning: "Manual Override and ABIL context both require domain knowledge. Use them when the dataset source and business conditions are known.",
    code: `{
  "events": [
    {
      "category": "Retention Objective",
      "description": "Protect premium banking customers",
      "severity": "HIGH"
    },
    {
      "category": "Market Signal",
      "description": "Competitor launched fee waiver campaign",
      "severity": "MEDIUM"
    }
  ]
}`,
  },
  {
    id: "routing",
    group: "Domains",
    title: "Domain Routing",
    eyebrow: "Manual control",
    icon: Route,
    body:
      "UCIF supports automatic sector detection, but production intake defaults to explicit confirmation. Analysts can choose Telecom, Banking, E-commerce, or Healthcare after the CSV schema is parsed.",
    bullets: [
      "Use Auto-Route when the uploaded schema is unambiguous.",
      "Use Manual Override when the dataset comes from a known industry.",
      "Routing evidence remains visible in the workspace.",
    ],
  },
  {
    id: "coverage",
    group: "Readiness",
    title: "Coverage Intelligence",
    eyebrow: "Preflight",
    icon: Compass,
    body:
      "Coverage intelligence measures whether the dataset has enough customer evidence for reliable churn scoring. It explains missing critical fields, recovered semantic matches, and confidence gaps before execution.",
    bullets: [
      "CSV parsing validates row and column shape.",
      "Semantic mapping confirms the framework found useful customer concepts.",
      "ABIL context gives the decision layer external business facts.",
    ],
  },
  {
    id: "decisions",
    group: "Action",
    title: "Decision Support",
    eyebrow: "Action layer",
    icon: ShieldCheck,
    body:
      "Predictions become useful only when they guide action. UCIF combines churn probability, risk tier, coverage, concept confidence, and ABIL signals into decision-ready recommendations.",
    bullets: [
      "Rows open into a slide-out evidence drawer.",
      "Contribution waterfall explains why a customer is at risk.",
      "Reports remain attached to the active run.",
    ],
  },
];

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="mt-5 overflow-hidden rounded-lg border border-border bg-zinc-950 text-zinc-100">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
        <span className="text-xs font-medium text-zinc-400">abil-context.json</span>
        <Button type="button" variant="ghost" size="sm" className="h-7 text-zinc-300 hover:bg-white/10 hover:text-white" onClick={copy}>
          {copied ? <Check className="mr-1.5 h-3.5 w-3.5" /> : <Clipboard className="mr-1.5 h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-6">
        <code>
          {code.split("\n").map((line) => (
            <span key={line} className={cn(line.includes('"severity"') ? "text-amber-200" : line.includes('"category"') ? "text-sky-200" : "text-zinc-100")}>
              {line}
              {"\n"}
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
}

export default function KnowledgePage() {
  const [query, setQuery] = useState("");
  const framework = useQuery({
    queryKey: ["framework"],
    queryFn: ({ signal }) => apiRequest<FrameworkInfo>("/api/v1/framework", {}, signal),
  });

  const filteredDocs = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return docs;
    return docs.filter((doc) => `${doc.title} ${doc.eyebrow} ${doc.body} ${doc.bullets.join(" ")}`.toLowerCase().includes(q));
  }, [query]);

  return (
    <PageShell className="gap-0 p-0">
      <div className="border-b border-border bg-background/90 px-5 py-6 backdrop-blur lg:px-8">
        <div className="mx-auto max-w-7xl">
          <p className="text-xs font-semibold uppercase tracking-widest text-primary">Documentation</p>
          <div className="mt-2 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
            <div>
              <h2 className="text-3xl font-semibold tracking-tight">UCIF Knowledge Center</h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
                Framework behavior, ABIL context design, domain routing, readiness checks, and decision support.
              </p>
            </div>
            <Badge variant="outline">v{framework.data?.framework_version || "live"}</Badge>
          </div>
          <div className="relative mt-6 max-w-xl">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search framework, ABIL, routing..." className="h-10 pl-9" />
          </div>
        </div>
      </div>

      <div className="mx-auto grid w-full max-w-7xl gap-8 px-5 py-8 lg:grid-cols-[220px_minmax(0,1fr)_220px] lg:px-8">
        <aside className="hidden lg:block">
          <nav className="sticky top-24 space-y-5">
            {["Framework", "Evidence", "Domains", "Readiness", "Action"].map((group) => (
              <div key={group}>
                <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{group}</p>
                {docs.filter((doc) => doc.group === group).map((doc) => (
                  <a key={doc.id} href={`#${doc.id}`} className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                    <doc.icon className="h-4 w-4" />
                    {doc.title}
                  </a>
                ))}
              </div>
            ))}
          </nav>
        </aside>

        <main className="min-w-0 space-y-6">
          {framework.error ? <ErrorBanner error={framework.error as Error} onRetry={() => framework.refetch()} /> : null}
          {framework.isLoading ? <LoadingState label="Loading framework docs..." /> : null}

          {filteredDocs.map((doc, index) => (
            <Reveal key={doc.id} id={doc.id} delay={index * 0.03} className="scroll-mt-24 border-b border-border pb-10">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-primary">{doc.eyebrow}</p>
                  <h3 className="mt-2 text-2xl font-semibold tracking-tight">{doc.title}</h3>
                </div>
                <doc.icon className="h-5 w-5 text-muted-foreground" />
              </div>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-muted-foreground">{doc.body}</p>
              {doc.warning ? (
                <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  <p className="flex items-center gap-2 font-semibold">
                    <TriangleAlert className="h-4 w-4" />
                    Operational warning
                  </p>
                  <p className="mt-2 leading-6">{doc.warning}</p>
                </div>
              ) : null}
              <ul className="mt-5 grid gap-2">
                {doc.bullets.map((bullet) => (
                  <li key={bullet} className="flex gap-3 text-sm leading-6">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
              {doc.code ? <CodeBlock code={doc.code} /> : null}
            </Reveal>
          ))}

          <Reveal id="live-service" className="scroll-mt-24 pb-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-primary">Live Service</p>
                <h3 className="mt-2 text-2xl font-semibold tracking-tight">Supported Industries and Modules</h3>
              </div>
              <FileText className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-sm font-semibold">Industries</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(framework.data?.supported_sectors || []).map((sector) => (
                    <span key={sector} className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-medium">
                      {sectorLabel(sector)}
                    </span>
                  ))}
                </div>
              </div>
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-sm font-semibold">Modules</p>
                <div className="mt-3 grid gap-2">
                  {(framework.data?.available_modules || []).slice(0, 8).map((moduleName) => (
                    <span key={moduleName} className="rounded-md border border-border bg-background px-3 py-2 text-xs capitalize text-muted-foreground">
                      {moduleName.replaceAll("_", " ")}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </Reveal>

          {filteredDocs.length === 0 ? (
            <div className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
              No documentation sections matched your search.
            </div>
          ) : null}
        </main>

        <aside className="hidden lg:block">
          <div className="sticky top-24 rounded-lg border border-border bg-card p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">On this page</p>
            <nav className="mt-3 grid gap-2">
              {[...filteredDocs, { id: "live-service", title: "Live Service" }].map((doc) => (
                <a key={doc.id} href={`#${doc.id}`} className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                  {doc.title}
                </a>
              ))}
            </nav>
          </div>
        </aside>
      </div>
    </PageShell>
  );
}
