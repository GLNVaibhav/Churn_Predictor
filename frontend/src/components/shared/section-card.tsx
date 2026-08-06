import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardAction,
} from "@/components/ui/card";

interface SectionCardProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
}

export function SectionCard({
  title,
  description,
  action,
  children,
  className,
  contentClassName,
}: SectionCardProps) {
  return (
    <Card className={cn("py-5", className)}>
      <CardHeader className="border-b border-border/60 px-5 pb-4">
        <CardTitle className="text-[15px] font-semibold">{title}</CardTitle>
        {description ? <CardDescription className="text-xs leading-5">{description}</CardDescription> : null}
        {action ? <CardAction>{action}</CardAction> : null}
      </CardHeader>
      <CardContent className={cn("px-5", contentClassName)}>{children}</CardContent>
    </Card>
  );
}
