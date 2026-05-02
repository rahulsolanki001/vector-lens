import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

const inputBase =
  "w-full bg-bg-raised border border-bg-border rounded-md text-tx-primary placeholder:text-tx-muted focus:outline-none focus:ring-2 focus:ring-tx-code/50 focus:border-tx-code/50 transition-colors";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function Input({ label, className = "", ...rest }: InputProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && <label className="text-xs text-tx-secondary">{label}</label>}
      <input className={`${inputBase} px-3 py-2 text-sm ${className}`} {...rest} />
    </div>
  );
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

export function Textarea({ label, className = "", ...rest }: TextareaProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && <label className="text-xs text-tx-secondary">{label}</label>}
      <textarea className={`${inputBase} px-3 py-2 text-sm resize-none ${className}`} {...rest} />
    </div>
  );
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: { value: string; label: string }[];
}

export function Select({ label, options, className = "", ...rest }: SelectProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && <label className="text-xs text-tx-secondary">{label}</label>}
      <select className={`${inputBase} px-3 py-2 text-sm ${className}`} {...rest}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
