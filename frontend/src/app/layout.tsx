import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppTopbar } from "@/components/layout/app-topbar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DevModeProvider } from "@/lib/context/dev-mode-context";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Universal Churn Intelligence Platform",
  description: "Enterprise dashboard for the Universal Churn Prediction Framework",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <TooltipProvider delay={150}>
          <DevModeProvider>
            <div className="flex h-screen w-full overflow-hidden bg-background">
              <AppSidebar />
              <div className="flex flex-1 flex-col overflow-hidden">
                <AppTopbar />
                {children}
              </div>
            </div>
          </DevModeProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}
