"use client";

import { usePathname } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppTopbar } from "@/components/layout/app-topbar";

export function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const reduceMotion = useReducedMotion();
  const standalone = pathname === "/" || pathname.startsWith("/signin");

  if (standalone) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-dvh min-h-0 w-full overflow-hidden bg-background print:block print:h-auto print:overflow-visible print:bg-white">
      <a href="#main-content" className="sr-only z-50 rounded-md bg-background px-3 py-2 text-sm font-medium text-foreground focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus-visible:ring-2 focus-visible:ring-ring">
        Skip to main content
      </a>
      <AppSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <AppTopbar />
        <motion.main
          id="main-content"
          key={pathname}
          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: [0.2, 0, 0, 1] }}
          className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden print:block print:overflow-visible"
        >
          {children}
        </motion.main>
      </div>
    </div>
  );
}
