"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Download, FileText, Gauge, Network, ShieldCheck, Sparkles } from "lucide-react";
import type { ReportCategory, ReportItem, ReportViewerContent } from "@/lib/types";
import { cn } from "@/lib/utils";

const sectorLabel: Record<string, string> = {
  telecom: "Telecom",
  banking: "Banking",
  healthcare: "Healthcare",
  ecommerce: "E-commerce",
};

const typeStyles: Record<string, string> = {
  "Execution Summary": "bg-blue-500/10 text-blue-400 border-blue-500/20",
  "Prediction Explanation": "bg-purple-500/10 text-purple-400 border-purple-500/20",
  "Business Reasoning": "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  "Drift Monitoring": "bg-amber-500/10 text-amber-400 border-amber-500/20",
};

const iconMap = {
  "shield-check": ShieldCheck,
  gauge: Gauge,
  sparkles: Sparkles,
  network: Network,
  "file-text": FileText,
};

interface ReportCategoryMeta {
  category: ReportCategory;
  description: string;
  reportCount: number;
  icon: keyof typeof iconMap;
}

export function ReportExplorer({
  categories,
  reports,
  getContent,
}: {
  categories: ReportCategoryMeta[];
  reports: ReportItem[];
  getContent: (category: ReportCategory) => ReportViewerContent;
}) {
  const [activeContent, setActiveContent] = useState<ReportViewerContent | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [loadingCategory, setLoadingCategory] = useState<string | null>(null);

  async function openCategory(category: ReportCategory) {
    setLoadingCategory(category);
    const content = getContent(category);
    setActiveContent(content);
    setDialogOpen(true);
    setLoadingCategory(null);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {categories.map((cat) => {
          const Icon = iconMap[cat.icon];
          return (
            <Card
              key={cat.category}
              className={cn(
                "cursor-pointer gap-3 py-5 transition-all hover:border-primary/50 hover:shadow-md",
                loadingCategory === cat.category && "opacity-60"
              )}
              onClick={() => openCategory(cat.category)}
            >
              <CardContent className="px-5">
                <div className="flex items-start justify-between">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                    <Icon className="h-4 w-4 text-primary" />
                  </div>
                  <Badge variant="outline" className="text-[11px]">
                    {cat.reportCount} reports
                  </Badge>
                </div>
                <p className="mt-3 text-sm font-semibold leading-tight">{cat.category}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{cat.description}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="overflow-hidden rounded-lg border border-border/60">
        <div className="flex flex-col divide-y divide-border/60">
          {reports.map((report) => (
            <div key={report.id} className="flex items-center justify-between gap-4 px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium">{report.title}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {sectorLabel[report.sector]} · {new Date(report.generatedAt).toLocaleString()} · {report.sizeKb} KB
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant="outline" className={typeStyles[report.type]}>
                  {report.type}
                </Badge>
                <Button variant="ghost" size="sm">
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
          {activeContent ? (
            <>
              <DialogHeader>
                <Badge variant="outline" className="w-fit text-[11px]">
                  {activeContent.category}
                </Badge>
                <DialogTitle className="mt-1">{activeContent.headline}</DialogTitle>
                <DialogDescription>{activeContent.summary}</DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-5">
                {activeContent.sections.map((section, idx) => (
                  <div key={section.heading}>
                    {idx > 0 ? <Separator className="mb-5" /> : null}
                    <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {section.heading}
                    </p>
                    <p className="text-sm leading-relaxed text-muted-foreground">{section.body}</p>
                    {section.metrics ? (
                      <div className="mt-3 grid grid-cols-3 gap-2">
                        {section.metrics.map((m) => (
                          <div key={m.label} className="rounded-lg border border-border/60 bg-muted/30 px-3 py-2">
                            <p className="truncate text-[10px] uppercase tracking-wide text-muted-foreground">
                              {m.label}
                            </p>
                            <p className="truncate text-sm font-semibold tabular-nums">{m.value}</p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
