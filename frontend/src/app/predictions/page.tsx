import { redirect } from "next/navigation";

export default function PredictionsPage() {
  redirect("/workspace?tab=prediction");
}
