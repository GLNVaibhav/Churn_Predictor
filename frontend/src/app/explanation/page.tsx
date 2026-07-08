"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ExplanationPage() {
  const router = useRouter();
  useEffect(() => { router.replace("/workspace?tab=reasoning"); }, [router]);
  return null;
}
