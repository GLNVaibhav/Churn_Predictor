"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DecisionIntelligencePage() {
  const router = useRouter();
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set("tab", "decisions");
    router.replace(`/workspace?${params.toString()}`);
  }, [router]);
  return null;
}
