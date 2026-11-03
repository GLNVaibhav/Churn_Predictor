import { cn } from "@/lib/utils";

export function PageShell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 flex-1 flex-col gap-5 overflow-y-auto bg-background p-4 sm:p-5 lg:p-6 print:overflow-visible print:bg-white print:p-0", className)}>
      {children}
    </div>
  );
}
