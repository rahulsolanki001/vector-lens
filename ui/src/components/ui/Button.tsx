import type { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost";
  size?: "sm" | "md";
  hint?: string;
  children: ReactNode;
}

export function Button({
  variant = "primary",
  size = "md",
  hint,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 font-medium rounded-md transition-all focus-visible:outline-none";
  const sizeClass =
    size === "sm"
      ? "px-3 py-1.5 text-sm h-7"
      : "px-3.5 py-2 text-sm h-8";

  const variantClass =
    variant === "primary"
      ? "btn-primary text-white"
      : "bg-transparent hover:bg-bg-raised text-tx-secondary hover:text-tx-primary border border-bg-border disabled:opacity-45 disabled:cursor-not-allowed";

  return (
    <button
      className={`${base} ${sizeClass} ${variantClass} ${className}`}
      disabled={disabled}
      {...rest}
    >
      {children}
      {hint && (
        <kbd className="ml-0.5 inline-flex h-4 items-center rounded border border-white/20 bg-white/10 px-1 font-mono text-[10px] text-white/70">
          {hint}
        </kbd>
      )}
    </button>
  );
}
