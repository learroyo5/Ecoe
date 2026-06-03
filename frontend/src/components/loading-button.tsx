"use client";

type Props = {
  type?: "submit" | "button";
  variant?: "primary" | "secondary";
  loading?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
  children: React.ReactNode;
};

export function LoadingButton({
  type = "button",
  variant = "primary",
  loading = false,
  disabled = false,
  onClick,
  className = "",
  children,
}: Props) {
  return (
    <button
      type={type}
      className={`${variant === "primary" ? "btn-primary" : "btn-secondary"} inline-flex items-center gap-2 ${className}`}
      disabled={disabled || loading}
      onClick={onClick}
    >
      {loading ? (
        <svg className="size-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      ) : null}
      {loading ? "Cargando..." : children}
    </button>
  );
}
