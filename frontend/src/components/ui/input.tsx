import * as React from "react";
import { cn } from "@/lib/utils";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-md border border-ws-border bg-ws-surface px-3 text-[14px] text-ws-primary",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ws-accent",
        className,
      )}
      {...props}
    />
  );
}

