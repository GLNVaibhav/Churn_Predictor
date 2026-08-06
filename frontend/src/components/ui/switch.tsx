"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

type SwitchProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> & {
  defaultChecked?: boolean;
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
};

export function Switch({ className, defaultChecked = false, checked, onCheckedChange, ...props }: SwitchProps) {
  const [internalChecked, setInternalChecked] = useState(defaultChecked);
  const active = checked ?? internalChecked;

  function toggle() {
    const next = !active;
    if (checked === undefined) setInternalChecked(next);
    onCheckedChange?.(next);
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={active}
      onClick={toggle}
      className={cn(
        "relative h-5 w-9 rounded-full border border-border bg-muted transition-colors focus-visible:ring-2 focus-visible:ring-ring/40 focus-visible:outline-none aria-checked:border-primary aria-checked:bg-primary",
        className,
      )}
      {...props}
    >
      <span
        className={cn(
          "absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-background shadow-sm transition-transform",
          active && "translate-x-4",
        )}
      />
    </button>
  );
}
