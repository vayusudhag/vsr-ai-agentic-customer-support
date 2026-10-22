import { AlertTriangle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-alert/20 bg-alert-soft px-4 py-3 text-sm text-alert">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span className="flex-1">{message}</span>
      {onRetry && <button className="font-medium underline underline-offset-2" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="flex items-center gap-2 py-10 text-sm text-ink/55"><Loader2 className="h-4 w-4 animate-spin" />{label}</div>;
}

const STATUS: Record<string, string> = {
  delivered: "bg-lagoon-soft text-lagoon-ink", shipped: "bg-blue-50 text-blue-700", in_transit: "bg-blue-50 text-blue-700",
  processing: "bg-ink/5 text-ink/70", cancelled: "bg-alert-soft text-alert", pending: "bg-amber-soft text-amber-ink",
  approved: "bg-lagoon-soft text-lagoon-ink", rejected: "bg-alert-soft text-alert", open: "bg-blue-50 text-blue-700",
};
export function Status({ value }: { value: string }) {
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS[value] ?? "bg-ink/5 text-ink/70"}`}>{value.replace("_", " ")}</span>;
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[26px] font-semibold leading-tight">{title}</h1>
        {sub && <p className="mt-1 max-w-2xl text-sm text-ink/60">{sub}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: "amber" | "alert" }) {
  const color = tone === "amber" ? "text-amber-ink" : tone === "alert" ? "text-alert" : "text-ink";
  return (
    <div className="bg-white px-5 py-4">
      <div className="text-[12.5px] text-ink/55">{label}</div>
      <div className={`num mt-1 font-display text-[28px] font-semibold leading-none ${color}`}>{value}</div>
      {hint && <div className="mt-1.5 text-xs text-ink/45">{hint}</div>}
    </div>
  );
}
