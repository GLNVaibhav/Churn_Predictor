"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function PredictionsPage() {
  const router = useRouter();
  useEffect(() => { router.replace("/workspace?tab=prediction"); }, [router]);
  return null;
}
