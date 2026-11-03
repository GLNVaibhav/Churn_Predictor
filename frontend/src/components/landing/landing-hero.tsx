"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { animate, createScope, createTimeline, onScroll, stagger } from "animejs";
import { ArrowDown, ArrowRight, ArrowUpRight, Check, Database, FileText, ScanSearch } from "lucide-react";
import AttractButton from "@/components/kokonutui/attract-button";
import { DataSourceBadge } from "@/components/shared/data-source-badge";

function WorkflowNetwork() {
  return (
    <svg className="hero-network" viewBox="0 0 760 560" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="network-line" x1="80" y1="80" x2="680" y2="500" gradientUnits="userSpaceOnUse">
          <stop stopColor="#777777" stopOpacity=".08" />
          <stop offset=".5" stopColor="#EDEDED" stopOpacity=".72" />
          <stop offset="1" stopColor="#A3A3A3" stopOpacity=".14" />
        </linearGradient>
        <radialGradient id="network-glow">
          <stop stopColor="#A3A3A3" stopOpacity=".13" />
          <stop offset="1" stopColor="#777777" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="410" cy="280" r="270" fill="url(#network-glow)" />
      <path className="hero-network__path" d="M64 370C160 370 170 160 282 160S400 360 500 360 590 194 696 194" stroke="url(#network-line)" strokeWidth="1.4" />
      <path className="hero-network__path" d="M110 110C202 110 210 280 306 280S420 112 522 112 620 412 708 412" stroke="url(#network-line)" strokeWidth="1.2" />
      <path className="hero-network__path" d="M54 486C164 486 186 394 280 394S388 218 490 218 586 306 710 306" stroke="url(#network-line)" strokeWidth="1.2" />
      <path className="hero-network__path" d="M178 54C178 150 380 146 380 250S206 336 206 470" stroke="url(#network-line)" strokeWidth="1" />
      {[[64, 370], [282, 160], [500, 360], [696, 194], [110, 110], [306, 280], [522, 112], [708, 412], [54, 486], [280, 394], [490, 218], [710, 306], [380, 250]].map(([cx, cy], index) => (
        <g key={`${cx}-${cy}`} className="hero-network__node" style={{ transformOrigin: `${cx}px ${cy}px` }}>
          <circle cx={cx} cy={cy} r={index === 12 ? 5 : 3} fill={index === 12 ? "#EDEDED" : "#A3A3A3"} />
          <circle cx={cx} cy={cy} r={index === 12 ? 13 : 8} stroke="#EDEDED" strokeOpacity=".22" />
        </g>
      ))}
    </svg>
  );
}

function ProductPreview() {
  return (
    <div className="hero-preview relative z-10 overflow-hidden rounded-2xl border border-white/10 bg-[#111111] shadow-[0_32px_90px_-42px_rgba(0,0,0,.9)]">
      <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3 sm:px-5">
        <div className="flex items-center gap-2" aria-hidden="true"><span className="h-2 w-2 rounded-full bg-white/20" /><span className="h-2 w-2 rounded-full bg-white/20" /><span className="h-2 w-2 rounded-full bg-white/20" /></div>
        <span className="truncate text-xs font-medium text-neutral-300">Analysis workspace</span>
        <DataSourceBadge kind="demonstration" label="Illustrative UI" />
      </div>
      <div className="grid md:grid-cols-[150px_minmax(0,1fr)]">
        <div className="hidden border-r border-white/10 p-4 md:block">
          <p className="text-[10px] font-semibold tracking-[.18em] text-neutral-500">WORKSPACE</p>
          <div className="mt-4 space-y-2 text-xs">
            <div className="rounded-md bg-white/10 px-2.5 py-2 text-white">Overview</div>
            <div className="px-2.5 py-2 text-neutral-500">Dataset</div>
            <div className="px-2.5 py-2 text-neutral-500">Predictions</div>
            <div className="px-2.5 py-2 text-neutral-500">Reports</div>
          </div>
        </div>
        <div className="min-w-0 p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-neutral-400">EXAMPLE VIEW · NOT AN EXECUTION</p>
              <h2 className="mt-1 text-base font-semibold text-white sm:text-lg">From upload to review</h2>
            </div>
            <span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] font-medium text-neutral-300">Demonstration</span>
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2 sm:gap-3">
            {[[Database, "Dataset", "Inspected"], [ScanSearch, "Analysis", "Submitted"], [FileText, "Results", "Reviewable"]].map(([Icon, title, state]) => {
              const StepIcon = Icon as typeof Database;
              return <div key={title as string} className="min-w-0 rounded-xl border border-white/10 bg-white/[.035] p-3">
                <StepIcon className="h-4 w-4 text-neutral-300" aria-hidden="true" />
                <p className="mt-3 truncate text-xs font-semibold text-neutral-100">{title as string}</p>
                <p className="mt-1 truncate text-[10px] text-neutral-500">{state as string}</p>
              </div>;
            })}
          </div>
          <div className="mt-3 rounded-xl border border-white/10 bg-[#090909] p-3 sm:p-4">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-medium text-neutral-200"><Check className="h-3.5 w-3.5 text-emerald-400" />Review returned analysis</div>
              <span className="text-[10px] text-neutral-500">Illustrative</span>
            </div>
            <div className="mt-3 h-px bg-white/10" />
            <p className="mt-3 text-[11px] leading-5 text-neutral-400">Actual fields, predictions, and recommendations depend on the uploaded dataset and the execution response.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function LandingHero() {
  const root = useRef<HTMLElement>(null);
  const router = useRouter();

  useEffect(() => {
    const section = root.current;
    if (!section || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const scope = createScope({ root: section }).add(() => {
      const paths = section.querySelectorAll<SVGPathElement>(".hero-network__path");
      paths.forEach((path) => {
        const length = path.getTotalLength();
        path.style.strokeDasharray = `${length}`;
        path.style.strokeDashoffset = `${length}`;
      });

      createTimeline({ defaults: { ease: "out(3)", duration: 700 } })
        .add(".hero-copy [data-enter]", { opacity: [0, 1], y: [20, 0], delay: stagger(80) }, 0)
        .add(".hero-preview", { opacity: [0, 1], y: [18, 0] }, 180)
        .add(".hero-network__node", { scale: [0.6, 1], opacity: [0.25, 1], duration: 500, delay: stagger(30) }, 420);

      const scroll = (target: Element) => onScroll({ target, sync: true, enter: "top top", leave: "bottom top" });
      animate(paths, { strokeDashoffset: 0, autoplay: scroll(section) });
      animate(".hero-copy", { y: [0, -96], opacity: [1, 0.34], autoplay: scroll(section) });
      animate(".hero-preview", { y: [0, 64], scale: [1, 0.94], opacity: [1, 0.5], autoplay: scroll(section) });
    });

    return () => scope.revert();
  }, []);

  return (
    <section ref={root} className="landing-hero relative isolate min-h-[calc(100svh-4.25rem)] overflow-hidden" aria-labelledby="landing-title">
      <div className="landing-hero__grid absolute inset-0" aria-hidden="true" />
      <div className="mx-auto grid min-h-[calc(100svh-4.25rem)] max-w-[1440px] items-center gap-12 px-5 py-14 sm:px-8 lg:grid-cols-[.93fr_1.07fr] lg:gap-16 lg:px-14 lg:py-16">
        <div className="hero-copy relative z-10 max-w-2xl">
          <p data-enter className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[.035] px-3 py-1.5 text-[11px] font-medium tracking-wide text-neutral-300">
            <span className="h-1.5 w-1.5 rounded-full bg-neutral-200" /> Customer retention intelligence
          </p>
          <h1 id="landing-title" className="mt-7 max-w-[13ch] text-[clamp(3.25rem,8vw,7.6rem)] font-medium leading-[.88] tracking-[-.075em] text-[#EDEDED]">
            <span data-enter className="block">From customer</span>
            <span data-enter className="block">data to</span>
            <span data-enter className="block text-neutral-500">business intelligence.</span>
          </h1>
          <p data-enter className="mt-7 max-w-lg text-sm leading-7 text-neutral-400 sm:text-base sm:leading-8">
            A considered workspace for inspecting customer datasets, reviewing churn analysis, and moving from returned evidence to business action.
          </p>
          <div data-enter className="mt-8 flex flex-wrap items-center gap-4">
            <AttractButton onClick={() => router.push("/upload")} className="h-11 min-w-40 rounded-md bg-white px-5 text-black hover:bg-neutral-200 dark:bg-white dark:text-black dark:hover:bg-neutral-200">
              Start an analysis <ArrowRight className="size-4" aria-hidden="true" />
            </AttractButton>
            <Link href="/dashboard" className="inline-flex h-11 items-center gap-2 rounded-md border border-white/15 px-4 text-sm font-medium text-neutral-200 transition-colors hover:bg-white/[.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white">
              Mission Control <ArrowUpRight className="size-4" aria-hidden="true" />
            </Link>
          </div>
          <div data-enter className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-neutral-500">
            <span>Dataset-driven analysis</span><span className="hidden size-1 rounded-full bg-neutral-700 sm:block" /><span>Results reflect the connected service response</span>
          </div>
          <a data-enter href="#editorial" className="mt-10 inline-flex items-center gap-2 text-xs font-medium text-neutral-400 transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white">
            Scroll to explore <ArrowDown className="size-3.5" aria-hidden="true" />
          </a>
        </div>

        <div className="relative mx-auto w-full max-w-[720px] lg:ml-auto">
          <WorkflowNetwork />
          <ProductPreview />
          <div className="relative z-10 mt-3 text-center text-[10px] tracking-wide text-neutral-500">Illustrative interface only · No live metrics or model outputs shown</div>
        </div>
      </div>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-white/15" />
    </section>
  );
}
