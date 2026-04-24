import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "default" | "outline";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ className, variant = "default", ...props }: ButtonProps) {
  return (
    <button
      type={props.type ?? "button"}
      className={cn(
        "inline-flex min-h-11 cursor-pointer items-center justify-center rounded-md px-4 py-2 text-[14px] font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ws-accent disabled:cursor-not-allowed disabled:opacity-60",
        variant === "default"
          ? "bg-ws-primary text-white hover:bg-[#16243f]"
          : "border border-ws-border bg-ws-surface text-ws-primary hover:bg-[#f0f3f9]",
        className,
      )}
      {...props}
    />
  );
}

