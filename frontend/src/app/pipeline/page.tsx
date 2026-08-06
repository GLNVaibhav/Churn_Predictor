import { redirect } from "next/navigation";

export default function PipelinePage() {
  redirect("/workspace?tab=pipeline");
}
