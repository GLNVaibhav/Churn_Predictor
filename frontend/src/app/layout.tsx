import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AppChrome } from "@/components/layout/app-chrome";
import { CommandMenu } from "@/components/layout/command-menu";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/lib/context/auth-context";
import { ThemeProvider } from "@/lib/context/theme-context";
import { ExecutionProvider } from "@/lib/context/execution-context";
import { AppQueryProvider } from "@/lib/query-provider";

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
  icons: {
    icon: "/ucif-logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <AppQueryProvider>
          <ExecutionProvider>
            <TooltipProvider delay={150}>
              <ThemeProvider>
                <AuthProvider>
                  <AppChrome>{children}</AppChrome>
                  <CommandMenu />
                </AuthProvider>
              </ThemeProvider>
            </TooltipProvider>
          </ExecutionProvider>
        </AppQueryProvider>
      </body>
    </html>
  );
}
