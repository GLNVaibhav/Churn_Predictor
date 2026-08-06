import { redirect } from "next/navigation";

export default function ExplanationPage() {
  redirect("/workspace?tab=reasoning");
}
