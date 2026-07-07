import { api } from "@/lib/api/client";
import { PageShell } from "@/components/layout/page-shell";
import { SectionCard } from "@/components/shared/section-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { UploadCloud, FileSpreadsheet, ArrowRight } from "lucide-react";
import Link from "next/link";

const typeStyles: Record<string, string> = {
  numeric: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  categorical: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  boolean: "bg-teal-500/10 text-teal-400 border-teal-500/20",
  text: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  date: "bg-orange-500/10 text-orange-400 border-orange-500/20",
};

export default async function UploadPage() {
  const preview = await api.upload.getPreview();

  return (
    <PageShell>
      <SectionCard title="Upload a Dataset" description="Any schema shape is accepted — sector and field mapping are resolved automatically downstream.">
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border/70 bg-muted/20 px-6 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <UploadCloud className="h-6 w-6 text-primary" />
          </div>
          <div>
            <p className="text-sm font-medium">Drag and drop a CSV file, or click to browse</p>
            <p className="mt-1 text-xs text-muted-foreground">Mock upload — no file is processed in Phase 1</p>
          </div>
          <Button variant="outline" size="sm" className="mt-2">
            Browse files
          </Button>
        </div>
      </SectionCard>

      <SectionCard
        title="Last Uploaded Dataset (Mock)"
        description="Preview of the most recent ingested file"
        action={
          <Link href="/pipeline">
            <Button size="sm">
              Run Analysis Pipeline
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        }
      >
        <div className="flex flex-wrap items-center gap-4 rounded-lg border border-border/60 bg-muted/20 p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <FileSpreadsheet className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1 min-w-[180px]">
            <p className="text-sm font-medium">{preview.fileName}</p>
            <p className="text-xs text-muted-foreground">
              {preview.rowCount.toLocaleString()} rows · {preview.columnCount} columns
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Detected sector</p>
            <Badge variant="outline" className="mt-1 capitalize">
              {preview.detectedSector} · {preview.detectionConfidence}% confidence
            </Badge>
          </div>
        </div>

        <div className="mt-5 overflow-hidden rounded-lg border border-border/60">
          <table className="w-full text-sm">
            <thead className="bg-muted/40">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2.5 font-medium">Column</th>
                <th className="px-4 py-2.5 font-medium">Inferred Type</th>
                <th className="px-4 py-2.5 font-medium">Null %</th>
                <th className="px-4 py-2.5 font-medium">Sample Values</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {preview.columns.map((col) => (
                <tr key={col.name}>
                  <td className="px-4 py-2.5 font-mono text-xs">{col.name}</td>
                  <td className="px-4 py-2.5">
                    <Badge variant="outline" className={typeStyles[col.inferredType]}>
                      {col.inferredType}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">{col.nullPercentage}%</td>
                  <td className="px-4 py-2.5 text-muted-foreground">
                    {col.sampleValues.join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </PageShell>
  );
}
