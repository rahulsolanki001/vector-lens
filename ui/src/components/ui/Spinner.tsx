interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeClass = { sm: "h-4 w-4", md: "h-5 w-5", lg: "h-7 w-7" };

export function Spinner({ size = "md", className = "" }: SpinnerProps) {
  return (
    <span
      className={`inline-block rounded-full border-2 border-bg-border border-t-accent animate-spin ${sizeClass[size]} ${className}`}
    />
  );
}
