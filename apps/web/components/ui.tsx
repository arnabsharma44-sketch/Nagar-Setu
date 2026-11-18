"use client";

import Link from "next/link";
import { humanise, statusTone } from "@/lib/format";

export type Tone = "command" | "admin";

const SURFACE: Record<Tone, string> = {
  command: "rounded-xl border border-[#1e2b3c] bg-[#0f1723] text-slate-200",
  admin: "rounded-xl border border-[#dfe6ee] bg-white text-slate-900",
};

const MUTED: Record<Tone, string> = {
  command: "text-slate-400",
  admin: "text-slate-500",
};

const HEADING: Record<Tone, string> = {
  command: "text-slate-100",
  admin: "text-slate-900",
};

const BORDER: Record<Tone, string> = {
  command: "border-[#1e2b3c]",
  admin: "border-[#dfe6ee]",
};

const ROW_HOVER: Record<Tone, string> = {
  command: "hover:bg-[#131e2c]",
  admin: "hover:bg-slate-50",
};

const INPUT: Record<Tone, string> = {
  command:
    "w-full rounded-lg border border-[#243449] bg-[#0b1320] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500",
  admin:
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400",
};

export function Card({
  tone,
  children,
  className = "",
}: {
  tone: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return <section className={`${SURFACE[tone]} ${className}`}>{children}</section>;
}

export function CardHeader({
  title,
  description,
  actions,
  tone,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  tone: Tone;
}) {
  return (
    <div className={`flex flex-wrap items-start justify-between gap-3 border-b ${BORDER[tone]} px-4 py-3`}>
      <div>
        <h2 className={`text-sm font-semibold ${HEADING[tone]}`}>{title}</h2>
        {description ? <p className={`mt-0.5 text-xs ${MUTED[tone]}`}>{description}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  tone,
  actions,
  breadcrumb,
}: {
  title: string;
  description?: string;
  tone: Tone;
  actions?: React.ReactNode;
  breadcrumb?: { label: string; href: string };
}) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        {breadcrumb ? (
          <Link className={`text-xs ${MUTED[tone]} hover:underline`} href={breadcrumb.href}>
            ← {breadcrumb.label}
          </Link>
        ) : null}
        <h1 className={`text-xl font-semibold tracking-tight ${HEADING[tone]}`}>{title}</h1>
        {description ? <p className={`mt-1 max-w-3xl text-sm ${MUTED[tone]}`}>{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export function StatusBadge({ status, label }: { status: string | null | undefined; label?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${statusTone(status)}`}
    >
      {label ?? humanise(status)}
    </span>
  );
}

export function MetricCard({
  label,
  value,
  hint,
  tone,
  emphasis = "default",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone: Tone;
  emphasis?: "default" | "warn" | "danger";
}) {
  const accent =
    emphasis === "danger"
      ? "border-l-rose-500"
      : emphasis === "warn"
        ? "border-l-amber-500"
        : tone === "command"
          ? "border-l-sky-500"
          : "border-l-blue-600";
  return (
    <div className={`${SURFACE[tone]} border-l-4 ${accent} px-4 py-3`}>
      <p className={`text-xs uppercase tracking-wide ${MUTED[tone]}`}>{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${HEADING[tone]}`}>{value}</p>
      {hint ? <p className={`mt-1 text-xs ${MUTED[tone]}`}>{hint}</p> : null}
    </div>
  );
}

export function DataTable({
  tone,
  head,
  children,
  empty,
  caption,
}: {
  tone: Tone;
  head: string[];
  children: React.ReactNode;
  empty?: string;
  caption?: string;
}) {
  const hasRows = Array.isArray(children) ? children.flat().filter(Boolean).length > 0 : Boolean(children);
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-full text-sm">
        {caption ? <caption className={`px-4 pb-2 text-left text-xs ${MUTED[tone]}`}>{caption}</caption> : null}
        <thead>
          <tr className={`border-b ${BORDER[tone]} text-left text-xs uppercase tracking-wide ${MUTED[tone]}`}>
            {head.map((label) => (
              <th key={label} className="whitespace-nowrap px-4 py-2 font-medium">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={`divide-y ${BORDER[tone]}`}>
          {hasRows ? (
            children
          ) : (
            <tr>
              <td colSpan={head.length} className={`px-4 py-8 text-center text-sm ${MUTED[tone]}`}>
                {empty ?? "No records yet."}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function Row({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return <tr className={ROW_HOVER[tone]}>{children}</tr>;
}

export function EmptyState({
  tone,
  title,
  description,
  action,
}: {
  tone: Tone;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className={`flex flex-col items-center justify-center gap-2 px-6 py-12 text-center ${MUTED[tone]}`}>
      <p className={`text-sm font-medium ${HEADING[tone]}`}>{title}</p>
      <p className="max-w-md text-sm">{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({
  tone,
  message,
  onRetry,
}: {
  tone: Tone;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-start gap-3 px-4 py-6 text-sm">
      <p className="flex items-center gap-2 font-medium text-rose-600">
        <span aria-hidden>⚠</span> Something went wrong
      </p>
      <p className={MUTED[tone]}>{message}</p>
      {onRetry ? (
        <Button tone={tone} variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

export function LoadingRows({ tone, label = "Loading…" }: { tone: Tone; label?: string }) {
  return (
    <div className={`flex items-center gap-2 px-4 py-6 text-sm ${MUTED[tone]}`} role="status" aria-live="polite">
      <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-current opacity-60" />
      {label}
    </div>
  );
}

export function PermissionNotice({ tone, permission }: { tone: Tone; permission: string }) {
  return (
    <Card tone={tone}>
      <EmptyState
        tone={tone}
        title="You do not have access to this view"
        description={`Your role does not include the ${permission} permission. Ask an administrator if you need access.`}
      />
    </Card>
  );
}

export function DemoBanner({ tone }: { tone: Tone }) {
  const classes =
    tone === "command"
      ? "border-amber-500/40 bg-amber-500/10 text-amber-200"
      : "border-amber-400 bg-amber-50 text-amber-900";
  return (
    <div className={`rounded-lg border px-3 py-2 text-xs ${classes}`} role="note">
      <strong>DEMO ENVIRONMENT</strong> — synthetic records and generated sample footage. Not real
      city statistics. AI output is a candidate observation until a human reviews it.
    </div>
  );
}

export function Button({
  tone,
  variant = "primary",
  children,
  onClick,
  type = "button",
  disabled,
  className = "",
}: {
  tone: Tone;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  children: React.ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
  className?: string;
}) {
  const variants: Record<string, string> = {
    primary:
      tone === "command"
        ? "bg-sky-500 text-slate-950 hover:bg-sky-400"
        : "bg-blue-700 text-white hover:bg-blue-600",
    secondary:
      tone === "command"
        ? "border border-[#243449] bg-[#131e2c] text-slate-200 hover:bg-[#1a2837]"
        : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    danger: "bg-rose-600 text-white hover:bg-rose-500",
    ghost:
      tone === "command"
        ? "text-sky-300 hover:bg-[#131e2c]"
        : "text-blue-700 hover:bg-slate-100",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  tone,
  hint,
  error,
  children,
  htmlFor,
}: {
  label: string;
  tone: Tone;
  hint?: string;
  error?: string;
  children: React.ReactNode;
  htmlFor?: string;
}) {
  return (
    <label className="block text-sm" htmlFor={htmlFor}>
      <span className={`mb-1 block font-medium ${HEADING[tone]}`}>{label}</span>
      {children}
      {hint && !error ? <span className={`mt-1 block text-xs ${MUTED[tone]}`}>{hint}</span> : null}
      {error ? <span className="mt-1 block text-xs text-rose-600">{error}</span> : null}
    </label>
  );
}

export function Input({
  tone,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { tone: Tone }) {
  return <input {...props} className={`${INPUT[tone]} ${props.className ?? ""}`} />;
}

export function Textarea({
  tone,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { tone: Tone }) {
  return <textarea {...props} className={`${INPUT[tone]} ${props.className ?? ""}`} />;
}

export function Select({
  tone,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement> & { tone: Tone }) {
  return (
    <select {...props} className={`${INPUT[tone]} ${props.className ?? ""}`}>
      {children}
    </select>
  );
}

export function KeyValue({ tone, items }: { tone: Tone; items: Array<[string, React.ReactNode]> }) {
  return (
    <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className={`text-xs uppercase tracking-wide ${MUTED[tone]}`}>{label}</dt>
          <dd className={`mt-0.5 ${HEADING[tone]}`}>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function TagList({ tone, items, emptyLabel = "None recorded" }: { tone: Tone; items: string[]; emptyLabel?: string }) {
  if (!items.length) return <p className={`text-sm ${MUTED[tone]}`}>{emptyLabel}</p>;
  return (
    <ul className={`flex flex-wrap gap-1.5 text-xs ${MUTED[tone]}`}>
      {items.map((item) => (
        <li
          key={item}
          className={`rounded px-2 py-0.5 ${tone === "command" ? "bg-[#16222f] text-slate-300" : "bg-slate-100 text-slate-700"}`}
        >
          {item}
        </li>
      ))}
    </ul>
  );
}
