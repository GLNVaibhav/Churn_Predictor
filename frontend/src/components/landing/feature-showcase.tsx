"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import { createScope, createTimeline, onScroll, stagger } from "animejs";
import { ArrowUpRight, BrainCircuit, ChartNoAxesCombined, ClipboardList, Database, FileCheck2, ScanSearch, ShieldCheck, type LucideIcon } from "lucide-react";

const workflows: {
  number: string;
  title: string;
  description: string;
  href: string;
  icon: LucideIcon;
  label: string;
  visual: string;
  layout: string;
}[] = [
  { number: "01", title: "Dataset Intelligence", description: "Inspect file structure, data types, missingness, and coverage before creating an analysis run.", href: "/upload", icon: Database, label: "Prepare data", visual: "file", layout: "lg:col-span-7" },
  { number: "02", title: "Universal Analysis", description: "Confirm a supported sector and submit a customer dataset through the analysis workflow.", href: "/upload", icon: ScanSearch, label: "Create a run", visual: "flow", layout: "lg:col-span-5" },
  { number: "03", title: "Churn Predictions", description: "Review the prediction fields and risk outputs returned for a completed execution.", href: "/workspace?tab=predictions", icon: BrainCircuit, label: "Returned results", visual: "nodes", layout: "lg:col-span-4" },
  { number: "04", title: "Diagnostic Intelligence", description: "Inspect diagnostics and explanation fields when they are present in the result.", href: "/workspace?tab=diagnostics", icon: ShieldCheck, label: "Evidence review", visual: "trace", layout: "lg:col-span-4" },
  { number: "05", title: "Business Intelligence", description: "Review business summaries and recommendations included by the analysis service.", href: "/workspace?tab=business", icon: ChartNoAxesCombined, label: "Business context", visual: "layers", layout: "lg:col-span-4" },
  { number: "06", title: "Decision Intelligence", description: "Explore decision-readiness information and returned action guidance in the workspace.", href: "/workspace?tab=business", icon: ClipboardList, label: "Decision support", visual: "decision", layout: "lg:col-span-5" },
  { number: "07", title: "Reports", description: "Open the report center to view and export available analysis outputs.", href: "/reports", icon: FileCheck2, label: "Available reports", visual: "report", layout: "lg:col-span-7" },
];

function FeatureMark({ kind }: { kind: string }) {
  if (kind === "file") return <div className="feature-mark feature-mark--file"><span /><span /><span /><span /><span /><span /></div>;
  if (kind === "flow") return <div className="feature-mark feature-mark--flow"><i /><i /><i /><i /><i /><i /><i /></div>;
  if (kind === "nodes") return <div className="feature-mark feature-mark--nodes"><i /><i /><i /><i /><i /></div>;
  if (kind === "trace") return <div className="feature-mark feature-mark--trace"><i /><i /><i /></div>;
  if (kind === "layers") return <div className="feature-mark feature-mark--layers"><i /><i /><i /></div>;
  if (kind === "decision") return <div className="feature-mark feature-mark--decision"><i /><i /><i /><i /></div>;
  return <div className="feature-mark feature-mark--report"><i /><i /><i /><i /><i /><i /></div>;
}

export function FeatureShowcase() {
  const reduceMotion = useReducedMotion();
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const section = root.current;
    if (!section || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const scope = createScope({ root: section }).add(() => {
      createTimeline({
        autoplay: onScroll({ target: section, sync: true, enter: "top bottom", leave: "bottom top" }),
        defaults: { ease: "out(3)" },
      }).add(".feature-card", { opacity: [0, 1], y: [26, 0], delay: stagger(90), duration: 420 }, 0);
    });
    return () => scope.revert();
  }, []);

  return (
    <section ref={root} id="product" className="feature-showcase relative overflow-hidden bg-[#111111] py-24 text-[#EDEDED] sm:py-32" aria-labelledby="product-title">
      <div className="mx-auto max-w-[1440px] px-5 sm:px-8 lg:px-14">
        <div className="mb-12 flex flex-col justify-between gap-6 lg:mb-16 lg:flex-row lg:items-end">
          <div className="max-w-3xl">
            <p className="text-[10px] font-semibold uppercase tracking-[.22em] text-neutral-500">Inside the platform</p>
            <h2 id="product-title" className="mt-4 text-[clamp(2.4rem,5.7vw,5.6rem)] font-medium leading-[.92] tracking-[-.065em]">Seven perspectives.<br /><span className="text-neutral-500">One connected workflow.</span></h2>
          </div>
          <p className="max-w-md text-sm leading-7 text-neutral-400">Explore the product areas that UCIF exposes today. Returned findings vary with the dataset and the connected service response.</p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-12 lg:gap-4">
          {workflows.map((item, index) => {
            const Icon = item.icon;
            return (
              <motion.div
                key={item.number}
                layout
                transition={{ duration: 0.3, ease: [0.2, 0, 0, 1] }}
                whileHover={reduceMotion ? undefined : { y: -5 }}
                whileTap={reduceMotion ? undefined : { scale: 0.99 }}
                className={`${item.layout} ${index === 0 || index === 6 ? "sm:col-span-2" : ""}`}
              >
                <Link href={item.href} className="feature-card group relative flex min-h-[300px] h-full flex-col justify-between overflow-hidden rounded-2xl border border-white/[.11] bg-[#191919] p-5 outline-none transition-colors hover:border-white/30 focus-visible:ring-2 focus-visible:ring-white sm:p-7">
                  <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/[.035] via-transparent to-transparent opacity-80" aria-hidden="true" />
                  <div className="relative flex items-start justify-between gap-5">
                    <div className="max-w-md">
                      <span className="inline-flex size-10 items-center justify-center rounded-xl border border-white/10 bg-white/[.045] text-neutral-200"><Icon className="size-4" aria-hidden="true" /></span>
                      <h3 className="mt-5 text-lg font-medium tracking-tight sm:text-xl">{item.title}</h3>
                      <p className="mt-2 max-w-md text-sm leading-6 text-neutral-400">{item.description}</p>
                    </div>
                    <span className="font-mono text-[10px] tracking-[.2em] text-neutral-600">{item.number}</span>
                  </div>
                  <div className="relative mt-8 flex min-h-[82px] items-end justify-between gap-4">
                    <FeatureMark kind={item.visual} />
                    <span className="flex shrink-0 items-center gap-2 text-[10px] font-medium uppercase tracking-[.13em] text-neutral-500 transition-colors group-hover:text-neutral-200">
                      {item.label}<ArrowUpRight className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden="true" />
                    </span>
                  </div>
                  <span className="sr-only">Open {item.title}</span>
                </Link>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
