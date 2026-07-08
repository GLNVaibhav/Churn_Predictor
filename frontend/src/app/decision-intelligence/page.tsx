"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DecisionIntelligencePage() {
  const router = useRouter();
  useEffect(() => { router.replace("/workspace?tab=decision"); }, [router]);
  return null;
}
