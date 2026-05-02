import type { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost";
  size?: "sm" | "md";
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const base = "inline-flex items-center justify-center gap-2 font-medium rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent";
  const sizeClass = size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2 text-base";
  const variantClass =
    variant === "primary"
      ? "bg-accent hover:bg-accent-hover text-white disabled:opacity-50 disabled:cursor-not-allowed"
      : "bg-transparent hover:bg-bg-raised text-tx-secondary hover:text-tx-primary border border-bg-border disabled:opacity-50 disabled:cursor-not-allowed";

  return (
    <button
      className={`${base} ${sizeClass} ${variantClass} ${className}`}
      disabled={disabled}
      {...rest}
    >
      {children}
    </button>
  );
}
