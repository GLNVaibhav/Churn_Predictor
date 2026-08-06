"use client";

import { usePathname } from "next/navigation";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppTopbar } from "@/components/layout/app-topbar";

export function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const standalone = pathname === "/" || pathname.startsWith("/signin");

  if (standalone) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <AppSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <AppTopbar />
        {children}
      </div>
    </div>
  );
}
