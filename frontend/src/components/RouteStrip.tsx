import { Wrench, ChevronRight } from "lucide-react";
import type { MessageMeta } from "../lib/api";

const AGENTS: Record<string, { label: string; color: string }> = {
  supervisor: { label: "Supervisor", color: "bg-agent-supervisor" },
  order_agent: { label: "Orders", color: "bg-agent-order" },
  knowledge_agent: { label: "Knowledge", color: "bg-agent-knowledge" },
  returns_agent: { label: "Returns & Refunds", color: "bg-agent-returns" },
  product_agent: { label: "Products", color: "bg-agent-product" },
  human_approval: { label: "Human approval", color: "bg-amber" },
};

/** The signature element: which agents handled a reply, and which tools they called. */
export function RouteStrip({ meta }: { meta: MessageMeta }) {
  const path = meta.agent_path ?? [];
  if (!path.length) return null;
  return (
    <div className="mt-2 space-y-1.5">
      <div className="route-in flex flex-wrap items-center gap-1 text-[11.5px] text-ink/70">
        {path.map((a, i) => (
          <span key={i} className="inline-flex items-center gap-1">
            {i > 0 && <ChevronRight className="h-3 w-3 text-ink/30" aria-hidden />}
            <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-2 py-0.5">
              <span className={`h-1.5 w-1.5 rounded-full ${AGENTS[a]?.color ?? "bg-ink/40"}`} />
              {AGENTS[a]?.label ?? a}
            </span>
          </span>
        ))}
        {meta.latency_ms != null && <span className="num ml-1 text-ink/45">{Math.round(meta.latency_ms)} ms</span>}
      </div>
      {!!meta.tools?.length && (
        <div className="flex flex-wrap gap-1">
          {meta.tools.map((t, i) => (
            <span key={i} title={`${t.latency_ms} ms`}
              className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[10.5px] ${t.success ? "bg-ink/[.04] text-ink/60" : "bg-alert-soft text-alert"}`}>
              <Wrench className="h-2.5 w-2.5" aria-hidden />{t.tool}()
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
