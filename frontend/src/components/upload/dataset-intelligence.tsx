"use client";

import { Fragment, useMemo, useState, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowDown, ArrowUp, ArrowUpDown, Braces, Database, FileSpreadsheet, Search, Table2 } from "lucide-react";
import BarChart from "@/components/charts/bar-chart";
import { Bar } from "@/components/charts/bar";
import { BarXAxis } from "@/components/charts/bar-x-axis";
import { ChartTooltip } from "@/components/charts/tooltip/chart-tooltip";
import RingChart from "@/components/charts/ring-chart";
import { Ring } from "@/components/charts/ring";
import { RingCenter } from "@/components/charts/ring-center";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { UploadedDatasetPreview } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  profile: UploadedDatasetPreview;
  browserFileSize: number | null;
  onBack: () => void;
  onContinue: () => void;
};

const series = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatBytes(bytes: number | null) {
  if (bytes === null) return "Not available";
  if (bytes < 1_000) return `${bytes} bytes`;
  if (bytes < 1_000_000) return `${(bytes / 1_000).toFixed(1)} KB`;
  return `${(bytes / 1_000_000).toFixed(2)} MB`;
}

function Panel({ title, eyebrow, children, className }: { title: string; eyebrow?: string; children: ReactNode; className?: string }) {
  return (
    <section className={cn("min-w-0 rounded-2xl border border-border/80 bg-card p-4 shadow-[var(--shadow-card)] sm:p-5", className)}>
      {eyebrow ? <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted-foreground">{eyebrow}</p> : null}
      <h2 className={cn("text-sm font-semibold", eyebrow && "mt-1")}>{title}</h2>
      {children}
    </section>
  );
}

export function DatasetIntelligence({ profile, browserFileSize, onBack, onContinue }: Props) {
  const reduceMotion = useReducedMotion();
  const [schemaQuery, setSchemaQuery] = useState("");
  const [sampleQuery, setSampleQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [numericColumn, setNumericColumn] = useState("");
  const [sort, setSort] = useState<{ key: "name" | "backendDtype" | "missingCount"; direction: "asc" | "desc" }>({ key: "name", direction: "asc" });
  const [expanded, setExpanded] = useState<string | null>(null);

  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    profile.columns.forEach((column) => {
      const type = column.inferredType || column.backendDtype || "Not reported";
      counts.set(type, (counts.get(type) || 0) + 1);
    });
    const ranked = [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
    const visible = ranked.length > 8
      ? [...ranked.slice(0, 7), ["Other types", ranked.slice(7).reduce((total, [, value]) => total + value, 0)] as [string, number]]
      : ranked;
    return visible.map(([name, value], index) => ({ name, value, color: series[index % series.length] }));
  }, [profile.columns]);

  const missingData = useMemo(() => profile.columns
    .filter((column) => column.missingCount !== null && column.missingCount > 0)
    .sort((a, b) => (b.missingCount || 0) - (a.missingCount || 0))
    .slice(0, 12)
    .map((column) => ({ name: column.name, missing: column.missingCount || 0 })), [profile.columns]);

  const numericColumns = useMemo(() => profile.columns.filter((column) => /int|float|double|decimal|number|numeric/i.test(column.inferredType || column.backendDtype)), [profile.columns]);
  const selectedNumericColumn = numericColumns.find((column) => column.name === numericColumn) || numericColumns[0];
  const previewDistribution = useMemo(() => {
    if (!selectedNumericColumn || profile.previewRows.length === 0) return [];
    const values = profile.previewRows
      .map((row) => row[selectedNumericColumn.name])
      .filter((value): value is string | number => typeof value === "number" || (typeof value === "string" && value.trim() !== ""))
      .map(Number)
      .filter(Number.isFinite);
    if (!values.length) return [];
    const min = values.reduce((current, value) => Math.min(current, value), Number.POSITIVE_INFINITY);
    const max = values.reduce((current, value) => Math.max(current, value), Number.NEGATIVE_INFINITY);
    const count = min === max ? 1 : 6;
    const width = (max - min) / count;
    const bins = Array.from({ length: count }, (_, index) => ({
      name: min === max ? String(min) : `${(min + index * width).toPrecision(4)}–${(min + (index + 1) * width).toPrecision(4)}`,
      records: 0,
    }));
    values.forEach((value) => {
      const index = min === max ? 0 : Math.min(count - 1, Math.floor((value - min) / width));
      bins[index].records += 1;
    });
    return bins;
  }, [profile.previewRows, selectedNumericColumn]);

  const filteredColumns = useMemo(() => {
    const query = schemaQuery.trim().toLowerCase();
    return profile.columns
      .filter((column) => !query || `${column.name} ${column.backendDtype}`.toLowerCase().includes(query))
      .filter((column) => {
        const dtype = (column.inferredType || column.backendDtype).toLowerCase();
        if (typeFilter === "all") return true;
        if (typeFilter === "numeric") return /int|float|double|decimal|number/.test(dtype);
        if (typeFilter === "text") return /object|string|category|text/.test(dtype);
        if (typeFilter === "boolean") return /bool/.test(dtype);
        return /date|time/.test(dtype);
      })
      .sort((a, b) => {
        const left = a[sort.key] ?? (sort.direction === "asc" ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY);
        const right = b[sort.key] ?? (sort.direction === "asc" ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY);
        const comparison = typeof left === "number" && typeof right === "number" ? left - right : String(left).localeCompare(String(right));
        return sort.direction === "asc" ? comparison : -comparison;
      });
  }, [profile.columns, schemaQuery, sort, typeFilter]);

  const sampleColumns = [...new Set([...profile.columns.map((column) => column.name), ...profile.previewRows.flatMap((row) => Object.keys(row))])];
  const sampleRows = useMemo(() => {
    const query = sampleQuery.trim().toLowerCase();
    return profile.previewRows
      .map((row, index) => ({ row, index }))
      .filter(({ row }) => !query || Object.values(row).some((value) => displayValue(value).toLowerCase().includes(query)))
      .slice(0, 20);
  }, [profile.previewRows, sampleQuery]);

  function changeSort(key: "name" | "backendDtype" | "missingCount") {
    setSort((current) => ({ key, direction: current.key === key && current.direction === "asc" ? "desc" : "asc" }));
  }

  function SortMark({ field }: { field: typeof sort.key }) {
    if (sort.key !== field) return <ArrowUpDown className="ml-1 inline h-3 w-3 opacity-50" aria-hidden="true" />;
    const Icon = sort.direction === "asc" ? ArrowUp : ArrowDown;
    return <Icon className="ml-1 inline h-3 w-3" aria-hidden="true" />;
  }

  return (
    <div className="space-y-5" aria-label="Dataset intelligence">
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: reduceMotion ? 0 : 0.25 }}
        className="rounded-2xl border border-border bg-muted/15 p-4 sm:p-5"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-card"><Database className="h-4 w-4" /></span>
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted-foreground">Dataset intelligence · API profile</p>
              <h2 className="mt-1 break-all text-base font-semibold">{profile.fileName}</h2>
              <p className="mt-1 text-xs text-muted-foreground">Uploaded file · {formatBytes(browserFileSize)} · Preview rows are returned by the upload service.</p>
            </div>
          </div>
          <Badge variant="outline">{profile.detectedSector || "Sector not reported"}</Badge>
        </div>
        {profile.sectorDetection ? (
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            {profile.sectorDetection.status === "DETECTED"
              ? `Automatic schema match: ${profile.sectorDetection.signatureHits} domain-specific column signatures.`
              : "Automatic sector is uncertain. Select Manual Override and confirm the industry before running analysis."}
          </p>
        ) : null}

        <dl className="mt-5 grid grid-cols-2 gap-2 lg:grid-cols-4">
          <Metric label="Rows" value={profile.rowCount.toLocaleString()} icon={<FileSpreadsheet className="h-3.5 w-3.5" />} />
          <Metric label="Columns" value={profile.columnCount.toLocaleString()} icon={<Braces className="h-3.5 w-3.5" />} />
          <Metric label="Missing values" value={profile.columns.some((column) => column.missingCount !== null) ? profile.columns.reduce((total, column) => total + (column.missingCount || 0), 0).toLocaleString() : "Not reported"} icon={<Database className="h-3.5 w-3.5" />} />
          <Metric label="Target column" value={profile.targetColumn || "Not returned"} icon={<Table2 className="h-3.5 w-3.5" />} />
        </dl>
        <p className="mt-3 text-[11px] leading-5 text-muted-foreground">Target details, duplicate counts, and a complete dataset download are not included in the current upload response. Missing counts are shown only when returned by the API.</p>
      </motion.div>

      {profile.warnings.length > 0 ? (
        <Panel title="Validation warnings" eyebrow={`${profile.warnings.length} returned by the upload API`}>
          <ul className="mt-3 space-y-2">{profile.warnings.map((warning, index) => <li key={`${index}-${warning}`} className="rounded-lg border border-amber-500/25 bg-amber-500/5 px-3 py-2 text-sm leading-5">{warning}</li>)}</ul>
        </Panel>
      ) : null}
      {profile.missingCritical.length > 0 ? (
        <Panel title="Domain coverage gaps" eyebrow="Missing critical fields returned by the upload API">
          <div className="mt-3 flex flex-wrap gap-2">{profile.missingCritical.map((field) => <Badge key={field} variant="outline">{field}</Badge>)}</div>
        </Panel>
      ) : null}

      <div className="grid min-w-0 gap-4 xl:grid-cols-2">
        <Panel title="Missing values by column" eyebrow="Dataset-level counts">
          {missingData.length ? (
            <div className="mt-3">
              <BarChart data={missingData} xDataKey="name" aspectRatio="1.8 / 1" margin={{ top: 14, right: 12, bottom: 34, left: 18 }} animationDuration={550}>
                <Bar dataKey="missing" fill="var(--chart-line-primary)" lineCap={4} showValue animate />
                <BarXAxis showAllLabels maxLabels={10} />
                <ChartTooltip />
              </BarChart>
              <p className="text-[10px] text-muted-foreground">Top {missingData.length} columns with missing observations. Counts use the API-reported dataset row total.</p>
            </div>
          ) : profile.columns.some((column) => column.missingCount !== null) ? (
            <ChartEmptyState>All returned columns have zero reported missing values.</ChartEmptyState>
          ) : <ChartEmptyState>Missing-value counts were not returned for this dataset.</ChartEmptyState>}
        </Panel>

        <Panel title="Column type composition" eyebrow="Backend inferred type where available">
          {typeCounts.length ? (
            <div className="mt-2 grid grid-cols-1 items-center gap-1 sm:grid-cols-[minmax(170px,.85fr)_minmax(0,1fr)]">
              <RingChart data={typeCounts.map((item) => ({ label: item.name, value: item.value, maxValue: Math.max(profile.columnCount, typeCounts.reduce((total, type) => total + type.value, 0), 1), color: item.color }))} size={190} strokeWidth={5} ringGap={2} baseInnerRadius={14} padding={7} className="mx-auto w-full max-w-[190px]">
                {typeCounts.map((item, index) => <Ring key={item.name} index={index} color={item.color} showGlow={false} />)}
                <RingCenter defaultLabel="columns" />
              </RingChart>
              <ul className="space-y-2 text-xs" aria-label="Column counts by reported data type">
                {typeCounts.map((item) => <li key={item.name} className="flex min-w-0 items-center justify-between gap-2"><span className="flex min-w-0 items-center gap-2"><span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: item.color }} aria-hidden="true"/><span className="truncate text-muted-foreground">{item.name}</span></span><span className="font-semibold tabular-nums">{item.value}</span></li>)}
              </ul>
            </div>
          ) : <ChartEmptyState>The upload response did not include a data-type map.</ChartEmptyState>}
        </Panel>
      </div>

      <Panel title="Numeric preview distribution" eyebrow="Returned preview only">
        {numericColumns.length ? (
          <>
            <label htmlFor="numeric-preview-column" className="sr-only">Choose numeric preview column</label>
            <select id="numeric-preview-column" value={selectedNumericColumn?.name || ""} onChange={(event) => setNumericColumn(event.target.value)} className="mt-3 h-9 max-w-full rounded-lg border border-input bg-background px-3 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              {numericColumns.map((column) => <option key={column.name} value={column.name}>{column.name}</option>)}
            </select>
            {previewDistribution.length ? (
              <div className="mt-2">
                <BarChart data={previewDistribution} xDataKey="name" aspectRatio="2.5 / 1" margin={{ top: 12, right: 12, bottom: 28, left: 16 }} animationDuration={500}>
                  <Bar dataKey="records" fill="var(--chart-line-primary)" lineCap={4} showValue animate />
                  <BarXAxis showAllLabels maxLabels={8} />
                  <ChartTooltip />
                </BarChart>
                <p className="text-[10px] text-muted-foreground">Counts are calculated from {profile.previewRows.length} API-returned preview records only; they do not describe the full uploaded dataset.</p>
              </div>
            ) : <ChartEmptyState>The selected numeric column has no numeric values in the returned preview.</ChartEmptyState>}
          </>
        ) : <ChartEmptyState>No numeric columns were identified from the API-reported data types.</ChartEmptyState>}
      </Panel>

      <Panel title="Schema explorer" eyebrow={`${filteredColumns.length} of ${profile.columns.length} columns`}>
        <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_180px]">
          <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true"/><Input value={schemaQuery} onChange={(event) => setSchemaQuery(event.target.value)} placeholder="Search column name or type" aria-label="Search schema columns" className="h-10 pl-9" /></div>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="h-10 rounded-lg border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label="Filter columns by data type">
            <option value="all">All data types</option><option value="numeric">Numeric</option><option value="text">Text / category</option><option value="boolean">Boolean</option><option value="date">Date / time</option>
          </select>
        </div>
        {profile.columns.length ? (
          <div className="mt-3 overflow-hidden rounded-xl border border-border">
            <div className="max-h-[440px] overflow-auto">
              <table className="w-full min-w-[700px] text-sm">
                <thead className="sticky top-0 z-10 bg-muted/90 text-left text-[10px] uppercase tracking-wider text-muted-foreground backdrop-blur"><tr>
                  <th className="px-3 py-3"><button type="button" onClick={() => changeSort("name")} className="font-semibold">Column <SortMark field="name"/></button></th>
                  <th className="px-3 py-3"><button type="button" onClick={() => changeSort("backendDtype")} className="font-semibold">Backend dtype <SortMark field="backendDtype"/></button></th>
                  <th className="px-3 py-3">Inferred type</th>
                  <th className="px-3 py-3 text-right">Non-null</th>
                  <th className="px-3 py-3 text-right"><button type="button" onClick={() => changeSort("missingCount")} className="font-semibold">Missing <SortMark field="missingCount"/></button></th>
                  <th className="px-3 py-3 text-right">Missing %</th><th className="px-3 py-3">Details</th>
                </tr></thead>
                <tbody className="divide-y divide-border/70">
                  {filteredColumns.map((column) => {
                    const hasMissing = column.missingCount !== null;
                    const nonNull = hasMissing ? Math.max(0, profile.rowCount - column.missingCount!) : null;
                    const isExpanded = expanded === column.name;
                    return <Fragment key={column.name}>
                      <tr className="hover:bg-muted/25">
                        <th scope="row" className="max-w-[220px] truncate px-3 py-3 text-left font-mono text-xs font-medium" title={column.name}>{column.name}</th>
                        <td className="px-3 py-3"><Badge variant="outline" className="font-mono text-[10px]">{column.backendDtype || "Not reported"}</Badge></td>
                        <td className="px-3 py-3 text-xs">{column.inferredType || "Not reported"}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{nonNull === null ? "Not reported" : nonNull.toLocaleString()}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{column.missingCount === null ? "Not reported" : column.missingCount.toLocaleString()}</td>
                        <td className="px-3 py-3 text-right tabular-nums">{column.missingPercentage === null ? "Not reported" : `${column.missingPercentage.toFixed(2)}%`}</td>
                        <td className="px-3 py-2"><Button type="button" variant="ghost" size="sm" aria-expanded={isExpanded} onClick={() => setExpanded(isExpanded ? null : column.name)}>{isExpanded ? "Hide" : "Inspect"}</Button></td>
                      </tr>
                      <AnimatePresence initial={false}>
                        {isExpanded ? <tr><td colSpan={7} className="bg-muted/20 px-4 py-3">
                          <motion.div initial={reduceMotion ? false : { opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={reduceMotion ? undefined : { opacity: 0, height: 0 }} transition={{ duration: reduceMotion ? 0 : 0.18 }} className="overflow-hidden text-xs">
                            <p className="font-medium">Returned preview values</p><p className="mt-1 break-words leading-5 text-muted-foreground">{column.sampleValues.length ? column.sampleValues.map((value) => value.length > 110 ? `${value.slice(0, 107)}…` : value).join(" · ") : "No non-empty values were returned in the preview."}</p>
                          </motion.div>
                        </td></tr> : null}
                      </AnimatePresence>
                    </Fragment>;
                  })}
                  {!filteredColumns.length ? <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-muted-foreground">No schema columns match this search and filter.</td></tr> : null}
                </tbody>
              </table>
            </div>
          </div>
        ) : <ChartEmptyState>The upload response did not include column metadata.</ChartEmptyState>}
      </Panel>

      <Panel title="Returned records" eyebrow={`${profile.previewRows.length} records in API preview`}>
        {sampleColumns.length && profile.previewRows.length ? (
          <>
            <div className="relative mt-3 max-w-md"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true"/><Input value={sampleQuery} onChange={(event) => setSampleQuery(event.target.value)} placeholder="Search returned preview records" aria-label="Search returned preview records" className="h-10 pl-9" /></div>
            <div className="mt-3 max-h-[380px] overflow-auto rounded-xl border border-border">
              <table className="w-full min-w-[720px] text-xs">
                <thead className="sticky top-0 z-10 bg-muted/90 text-left text-[10px] uppercase tracking-wider text-muted-foreground backdrop-blur"><tr><th className="px-3 py-3">Row</th>{sampleColumns.map((column) => <th key={column} className="max-w-[200px] truncate px-3 py-3" title={column}>{column}</th>)}</tr></thead>
                <tbody className="divide-y divide-border/70">{sampleRows.map(({ row, index }) => <tr key={index} className="hover:bg-muted/25"><th scope="row" className="px-3 py-2 font-mono text-muted-foreground">{index + 1}</th>{sampleColumns.map((column) => <td key={column} className="max-w-[240px] truncate px-3 py-2" title={displayValue(row[column])}>{displayValue(row[column])}</td>)}</tr>)}
                  {!sampleRows.length ? <tr><td colSpan={sampleColumns.length + 1} className="px-4 py-8 text-center text-sm text-muted-foreground">No returned rows match this search.</td></tr> : null}</tbody>
              </table>
            </div>
            <p className="mt-2 text-[10px] leading-5 text-muted-foreground">These are the actual records included in the upload response, not a locally generated sample. The table is limited to the returned preview.</p>
          </>
        ) : <ChartEmptyState>No sample records were included in the upload response.</ChartEmptyState>}
      </Panel>

      <div className="flex flex-wrap justify-between gap-3 border-t border-border pt-4"><Button variant="outline" onClick={onBack}>Replace dataset</Button><Button onClick={onContinue}>Configure analysis <span className="ml-2">→</span></Button></div>
    </div>
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return <div className="min-w-0 rounded-xl border border-border bg-background/70 p-3"><div className="flex items-center justify-between gap-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"><span>{label}</span>{icon}</div><p className="mt-2 truncate text-base font-semibold tabular-nums sm:text-lg">{value}</p></div>;
}

function ChartEmptyState({ children }: { children: ReactNode }) {
  return <div className="mt-3 flex min-h-[180px] items-center justify-center rounded-xl border border-dashed border-border bg-muted/15 p-6 text-center text-xs leading-5 text-muted-foreground">{children}</div>;
}
