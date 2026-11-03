"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function PipelinePage() {
  const router = useRouter();
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set("tab", "pipeline");
    router.replace(`/workspace?${params.toString()}`);
  }, [router]);
  return null;
}
