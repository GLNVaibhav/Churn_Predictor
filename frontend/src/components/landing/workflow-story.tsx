"use client";

import { useEffect, useRef } from "react";
import { animate, createScope, createTimeline, onScroll, stagger } from "animejs";
import { Activity, ArrowDown, ArrowRight, BrainCircuit, BriefcaseBusiness, Database, FileSearch } from "lucide-react";
import BackgroundPaths from "@/components/kokonutui/background-paths";

const stages = [
  { title: "Customer data", eyebrow: "01 / INPUT", description: "A customer dataset enters through the existing upload workflow." },
  { title: "Dataset intelligence", eyebrow: "02 / INSPECT", description: "UCIF inspects the file and reports the structure and coverage it can establish." },
  { title: "Churn predictions", eyebrow: "03 / ANALYZE", description: "The connected analysis service returns prediction fields for an execution." },
  { title: "Diagnostic intelligence", eyebrow: "04 / EXPLAIN", description: "Returned diagnostics and explanation fields become available for review." },
  { title: "Business intelligence", eyebrow: "05 / ACT", description: "Business summaries and decisions are shown when included in the service response." },
];

function StageIllustration() {
  return (
    <div className="story-visual relative mx-auto flex aspect-square max-w-[440px] items-center justify-center" data-active-stage="0" aria-hidden="true">
      <div className="story-visual__frame absolute inset-[7%] rounded-full border border-current/15" />
      <div className="story-visual__frame story-visual__frame--inner absolute inset-[20%] rounded-full border border-dashed border-current/20" />
      <svg className="absolute inset-[12%] h-[76%] w-[76%] overflow-visible" viewBox="0 0 400 400" fill="none">
            <path className="story-visual__route" d="M52 200C92 200 93 93 148 93S202 200 254 200 306 120 348 120" stroke="currentColor" strokeWidth="1.5" />
        <path className="story-visual__route" d="M54 300C95 300 109 250 157 250S209 135 257 135 310 286 348 286" stroke="currentColor" strokeOpacity=".42" strokeWidth="1.2" />
        {[{ x: 52, y: 200 }, { x: 148, y: 93 }, { x: 254, y: 200 }, { x: 348, y: 120 }, { x: 54, y: 300 }, { x: 157, y: 250 }, { x: 257, y: 135 }, { x: 348, y: 286 }].map((node, index) => (
          <g className="story-visual__node" data-story-node={index % stages.length} key={`${node.x}-${node.y}`}>
            <circle cx={node.x} cy={node.y} r="5" fill="currentColor" />
            <circle cx={node.x} cy={node.y} r="12" stroke="currentColor" strokeOpacity=".22" />
          </g>
        ))}
      </svg>
      <div className="story-object story-object--0" data-story-object="0"><Database className="size-10" strokeWidth={1.25} /><span>customer file</span></div>
      <div className="story-object story-object--1" data-story-object="1"><div className="story-table-lines"><i /><i /><i /><i /><i /><i /></div><span>dataset schema</span></div>
      <div className="story-object story-object--2" data-story-object="2"><BrainCircuit className="size-10" strokeWidth={1.25} /><span>prediction output</span></div>
      <div className="story-object story-object--3" data-story-object="3"><FileSearch className="size-10" strokeWidth={1.25} /><span>diagnostic evidence</span></div>
      <div className="story-object story-object--4" data-story-object="4"><BriefcaseBusiness className="size-10" strokeWidth={1.25} /><span>business decision</span></div>
      <div className="story-visual__caption absolute bottom-[4%] left-1/2 -translate-x-1/2 whitespace-nowrap font-mono text-[10px] uppercase tracking-[.17em] text-current/50">Dataset → evidence → decision</div>
    </div>
  );
}

export function EditorialInterlude() {
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const section = root.current;
    if (!section) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const scope = createScope({ root: section }).add(() => {
      const paths = section.querySelectorAll<SVGPathElement>(".editorial-route");
      paths.forEach((path) => {
        const length = path.getTotalLength();
        path.style.strokeDasharray = `${length}`;
        path.style.strokeDashoffset = `${length}`;
      });
      animate(".editorial-statement", {
        x: [-44, 24],
        opacity: [0.5, 1],
        autoplay: onScroll({ target: section, sync: true, enter: "bottom bottom", leave: "top top" }),
      });
      animate(paths, {
        strokeDashoffset: 0,
        autoplay: onScroll({ target: section, sync: true, enter: "bottom bottom", leave: "top top" }),
      });
    });
    return () => scope.revert();
  }, []);

  return (
    <section ref={root} id="editorial" className="editorial-interlude relative overflow-hidden bg-[#EDEDED] text-[#111111]" aria-labelledby="editorial-title">
      <div className="mx-auto grid min-h-[74svh] max-w-[1440px] items-center gap-8 px-5 py-20 sm:px-8 md:grid-cols-[1.2fr_.8fr] lg:px-14">
        <div className="editorial-statement relative z-10 max-w-4xl">
          <p className="text-[10px] font-semibold uppercase tracking-[.22em] text-neutral-500">The intelligence is in the journey</p>
          <h2 id="editorial-title" className="mt-7 text-[clamp(2.6rem,6vw,6.25rem)] font-medium leading-[.92] tracking-[-.07em]">
            Better decisions begin with <span className="text-neutral-400">better context.</span>
          </h2>
          <p className="mt-7 max-w-xl text-sm leading-7 text-neutral-600 sm:text-base">UCIF brings the dataset, returned analysis, diagnostics, and business context into a single reviewable workflow.</p>
        </div>
        <div className="relative mx-auto aspect-square w-full max-w-[430px] text-neutral-800" aria-hidden="true">
          <div className="absolute inset-[12%] rounded-full border border-neutral-300" />
          <div className="absolute inset-[27%] rounded-full border border-dashed border-neutral-300" />
          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 400 400" fill="none">
            <path className="editorial-route" d="M43 260C99 260 91 110 161 110S212 260 260 260 297 145 357 145" stroke="#555" strokeWidth="1.4" />
            <circle cx="43" cy="260" r="5" fill="#111" /><circle cx="161" cy="110" r="5" fill="#111" /><circle cx="260" cy="260" r="5" fill="#111" /><circle cx="357" cy="145" r="5" fill="#111" />
          </svg>
          <span className="absolute left-[3%] top-[61%] text-[9px] uppercase tracking-widest text-neutral-500">Data</span>
          <span className="absolute left-[37%] top-[22%] text-[9px] uppercase tracking-widest text-neutral-500">Analysis</span>
          <span className="absolute right-[1%] top-[30%] text-[9px] uppercase tracking-widest text-neutral-500">Decisions</span>
        </div>
      </div>
    </section>
  );
}

export function PinnedWorkflowStory() {
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const section = root.current;
    if (!section) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const sticky = section.querySelector<HTMLElement>(".story-sticky");
    const route = section.querySelector<SVGPathElement>(".story-visual__route");
    const progress = section.querySelector<HTMLElement>(".story-progress-fill");
    const scenes = [...section.querySelectorAll<HTMLElement>("[data-story-scene]")];
    const objects = [...section.querySelectorAll<HTMLElement>("[data-story-object]")];
    const nodes = [...section.querySelectorAll<HTMLElement>("[data-story-node]")];
    const steps = [...section.querySelectorAll<HTMLButtonElement>("[data-story-step]")];
    const title = section.querySelector<HTMLElement>("[data-story-title]");
    const description = section.querySelector<HTMLElement>("[data-story-description]");
    const counter = section.querySelector<HTMLElement>("[data-story-counter]");
    const visual = section.querySelector<HTMLElement>(".story-visual");
    if (!(sticky && route && progress && title && description && counter && visual)) return;

    let currentStage = -1;
    const setStage = (stageIndex: number) => {
      if (currentStage === stageIndex) return;
      currentStage = stageIndex;
      const stage = stages[stageIndex];
      visual.dataset.activeStage = String(stageIndex);
      title.textContent = stage.title;
      description.textContent = stage.description;
      counter.textContent = stage.eyebrow;
      scenes.forEach((scene, index) => {
        const active = index === stageIndex;
        scene.setAttribute("aria-hidden", String(!active));
        if (reduceMotion) {
          scene.classList.toggle("opacity-100", active);
          scene.classList.toggle("opacity-0", !active);
          scene.classList.toggle("pointer-events-none", !active);
        }
      });
      objects.forEach((object, index) => object.classList.toggle("is-active", index === stageIndex));
      steps.forEach((button, index) => {
        button.classList.toggle("is-active", index === stageIndex);
        if (index === stageIndex) button.setAttribute("aria-current", "step");
        else button.removeAttribute("aria-current");
      });
      nodes.forEach((node) => node.classList.toggle("is-active", Number(node.dataset.storyNode) === stageIndex));
    };

    const scrollToStage = (index: number) => {
      const distance = section.offsetHeight - window.innerHeight;
      window.scrollTo({ top: section.offsetTop + distance * (index / (stages.length - 1)), behavior: reduceMotion ? "auto" : "smooth" });
    };
    steps.forEach((button, index) => { button.onclick = () => scrollToStage(index); });
    setStage(0);

    if (reduceMotion) {
      let frame = 0;
      const updateStage = () => {
        frame = 0;
        const distance = Math.max(section.offsetHeight - window.innerHeight, 1);
        const scrollProgress = Math.max(0, Math.min(1, (window.scrollY - section.offsetTop) / distance));
        setStage(Math.min(stages.length - 1, Math.floor(scrollProgress * stages.length)));
        progress.style.transform = `scaleX(${scrollProgress})`;
      };
      const scheduleUpdate = () => {
        if (!frame) frame = window.requestAnimationFrame(updateStage);
      };
      window.addEventListener("scroll", scheduleUpdate, { passive: true });
      window.addEventListener("resize", scheduleUpdate);
      scheduleUpdate();
      return () => {
        window.removeEventListener("scroll", scheduleUpdate);
        window.removeEventListener("resize", scheduleUpdate);
        if (frame) window.cancelAnimationFrame(frame);
        steps.forEach((button) => { button.onclick = null; });
      };
    }

    const pathLength = route.getTotalLength();
    route.style.strokeDasharray = `${pathLength}`;
    route.style.strokeDashoffset = `${pathLength}`;

    const scope = createScope({ root: section }).add(() => {
      const timeline = createTimeline({
        autoplay: onScroll({
          target: section,
          sync: true,
          enter: "top top",
          leave: "bottom bottom",
          onUpdate: (observer) => {
            const stageIndex = Math.min(stages.length - 1, Math.floor(observer.progress * stages.length));
            progress.style.transform = `scaleX(${observer.progress})`;
            setStage(stageIndex);
          },
        }),
        defaults: { ease: "linear" },
      })
        .add(sticky, { backgroundColor: ["#EDEDED", "#E3E0DA"], color: ["#111111", "#111111"], duration: 700 }, 0)
        .add(sticky, { backgroundColor: ["#E3E0DA", "#CCC9C1"], color: ["#111111", "#111111"], duration: 700 }, 700)
        .add(sticky, { backgroundColor: ["#CCC9C1", "#3A3937"], color: ["#111111", "#EDEDED"], duration: 700 }, 1400)
        .add(sticky, { backgroundColor: ["#3A3937", "#090909"], color: ["#EDEDED", "#EDEDED"], duration: 700 }, 2100)
        .add(route, { strokeDashoffset: 0, duration: 2800 }, 0)
        .add(".story-stage-step", { opacity: [0.38, 1], x: [-10, 0], delay: stagger(70), duration: 430 }, 0);

      scenes.forEach((scene, index) => {
        if (index > 0) {
          const position = 360 + (index - 1) * 560;
          timeline
            .add(scenes[index - 1], { opacity: [1, 0], y: [0, -12], duration: 360 }, position)
            .add(scene, { opacity: [0, 1], y: [16, 0], duration: 360 }, position)
            .add(objects[index - 1], { opacity: [1, 0], scale: [1, 0.92], duration: 360 }, position)
            .add(objects[index], { opacity: [0, 1], scale: [0.92, 1], duration: 360 }, position);
        }
      });
    });

    return () => {
      steps.forEach((button) => { button.onclick = null; });
      scope.revert();
    };
  }, []);

  return (
    <section ref={root} id="workflow" className="story-scroll relative bg-[#EDEDED]" aria-label="UCIF workflow from customer data to business intelligence">
      <div className="story-sticky flex items-center overflow-hidden bg-[#EDEDED] text-[#111111]">
        <BackgroundPaths className="story-background absolute inset-0 h-full min-h-0 bg-transparent text-neutral-500 dark:bg-transparent" count={24} spread={0.72} angle={-5} speed={0.08} interactive />
        <div className="story-wash pointer-events-none absolute inset-0" aria-hidden="true" />
        <div className="relative z-10 mx-auto grid h-full w-full max-w-[1440px] items-center gap-0 px-5 py-2 sm:px-8 md:grid-cols-[.86fr_1.14fr] md:gap-8 md:py-8 lg:gap-16 lg:px-14">
          <div className="flex h-auto flex-col justify-center py-2 md:h-full md:py-8">
            <p className="story-kicker text-[10px] font-semibold uppercase tracking-[.22em] opacity-55">The UCIF workflow</p>
            <p data-story-counter className="mt-4 font-mono text-[10px] tracking-[.18em] opacity-55 md:mt-8">{stages[0].eyebrow}</p>
            <div className="relative mt-2 min-h-[136px] sm:min-h-[168px] md:mt-3">
              {stages.map((stage, index) => (
                <article key={stage.title} data-story-scene={index} className={`absolute inset-0 ${index === 0 ? "opacity-100" : "pointer-events-none opacity-0"}`} aria-hidden={index !== 0}>
                  <h2 className="max-w-xl text-[clamp(2.2rem,5.3vw,5.25rem)] font-medium leading-[.94] tracking-[-.065em]">{stage.title}</h2>
                  <p className="mt-4 max-w-md text-sm leading-6 opacity-65 sm:text-base">{stage.description}</p>
                </article>
              ))}
              <h2 data-story-title className="sr-only">{stages[0].title}</h2>
              <p data-story-description className="sr-only">{stages[0].description}</p>
            </div>
            <div className="mt-4 max-w-md md:mt-8" aria-label="Workflow stages">
              <div className="story-progress-track h-px w-full bg-current/20"><span className="story-progress-fill block h-full origin-left scale-x-0 bg-current" /></div>
              <ol className="mt-4 grid grid-cols-5 gap-1">
                {stages.map((stage, index) => (
                  <li key={stage.title}>
                    <button type="button" data-story-step={index} className={`story-stage-step block w-full text-left text-[9px] leading-4 transition-opacity hover:opacity-100 focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current sm:text-[10px] ${index === 0 ? "is-active opacity-100" : "opacity-45"}`} aria-label={`Scroll to stage ${index + 1}: ${stage.title}`} aria-current={index === 0 ? "step" : undefined}>
                      <span className="mb-1 block font-mono">0{index + 1}</span>
                      <span className="hidden sm:block">{stage.title}</span>
                      <span className="block truncate sm:hidden">{stage.title.split(" ")[0]}</span>
                    </button>
                  </li>
                ))}
              </ol>
            </div>
            <p className="mt-8 hidden items-center gap-2 text-[10px] uppercase tracking-[.14em] opacity-40 md:flex"><ArrowDown className="size-3" /> Continue scrolling to move through the stages</p>
          </div>

          <div className="relative mx-auto w-full max-w-[550px]">
            <StageIllustration />
            <div className="story-note mx-auto flex max-w-sm items-center justify-between gap-4 border-t border-current/15 pt-3 text-[10px] opacity-55">
              <span className="flex items-center gap-2"><Activity className="size-3.5" /> One reviewable workflow</span>
              <span className="flex items-center gap-2">Evidence → action <ArrowRight className="size-3.5" /></span>
            </div>
            <p className="sr-only">Workflow stage content depends on the data and returned execution response.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
