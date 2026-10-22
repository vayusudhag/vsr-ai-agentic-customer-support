import { useCallback, useEffect, useState } from "react";
import { Check, Loader2, RefreshCw, X } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from "recharts";
import { api, day, money, time } from "../lib/api";
import { ErrorNote, Loading, PageHeader, Stat, Status } from "../components/ui";

type Metrics = {
  total_conversations: number; total_customer_requests: number; pending_refund_approvals: number; completed_requests: number;
  refunds: { pending: number; approved: number; rejected: number }; return_requests: number; failed_tool_calls: number; total_tool_calls: number;
  avg_response_latency_ms: number | null; p95_response_latency_ms: number | null;
  agent_usage: { agent: string; count: number }[]; tool_usage: { tool: string; count: number; failures: number }[];
  intent_distribution: { intent: string; count: number }[]; recent_failures: { agent: string; tool: string | null; error: string; at: string }[];
};
type Refund = { refund_id: string; order_id: string; customer: string; customer_email: string; amount: number; order_total: number; reason: string;
  status: string; created_at: string; decided_at: string | null; approved_by: string | null; note: string | null; simulated_transaction_id: string | null };

const AGENT_COLORS: Record<string, string> = { supervisor: "#475569", order_agent: "#2563EB", knowledge_agent: "#0F766E", returns_agent: "#B7791F", product_agent: "#7C3AED" };
const label = (s: string) => s.replace(/_agent$/, "").replace(/_/g, " ");

function Decide({ r, onDone }: { r: Refund; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"" | "approved" | "rejected">("");
  const [err, setErr] = useState("");
  const go = async (decision: "approved" | "rejected") => {
    setBusy(decision); setErr("");
    try { await api(`/api/admin/refunds/${r.refund_id}/decision`, { method: "POST", body: JSON.stringify({ decision, note: note || null }) }); onDone(); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(""); }
  };
  return (
    <div className="space-y-2">
      <input className="input py-1.5 text-[13px]" placeholder="Note to customer (optional)" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} aria-label={`Note for ${r.refund_id}`} />
      <div className="flex gap-2">
        <button className="btn-primary flex-1 py-1.5 text-[13px]" disabled={!!busy} onClick={() => go("approved")}>{busy === "approved" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}Approve</button>
        <button className="btn-outline flex-1 py-1.5 text-[13px] hover:border-alert/40 hover:text-alert" disabled={!!busy} onClick={() => go("rejected")}>{busy === "rejected" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}Reject</button>
      </div>
      {err && <p className="text-xs text-alert">{err}</p>}
    </div>
  );
}

export default function AdminDashboard() {
  const [m, setM] = useState<Metrics | null>(null);
  const [refunds, setRefunds] = useState<Refund[]>([]);
  const [err, setErr] = useState("");
  const [updated, setUpdated] = useState<string>("");
  const load = useCallback(() => {
    setErr("");
    Promise.all([api<Metrics>("/api/admin/metrics"), api<Refund[]>("/api/admin/refunds")])
      .then(([a, b]) => { setM(a); setRefunds(b); setUpdated(new Date().toISOString()); }).catch((e) => setErr(e.message));
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);
  const pending = refunds.filter((r) => r.status === "pending");
  const decided = refunds.filter((r) => r.status !== "pending").slice(0, 8);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
      <PageHeader title="VSR AI Dashboard" sub="Every number is computed live from conversations, refunds and agent execution logs."
        actions={<button className="btn-outline" onClick={load}><RefreshCw className="h-4 w-4" />Refresh{updated && <span className="text-xs text-ink/45">{time(updated)}</span>}</button>} />
      {err && <div className="mb-4"><ErrorNote message={err} onRetry={load} /></div>}
      {!m ? <Loading label="Loading metrics" /> : <>
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line md:grid-cols-4 lg:grid-cols-7">
          <Stat label="Conversations" value={m.total_conversations} />
          <Stat label="Customer requests" value={m.total_customer_requests} />
          <Stat label="Pending approvals" value={m.pending_refund_approvals} tone={m.pending_refund_approvals ? "amber" : undefined} />
          <Stat label="Completed requests" value={m.completed_requests} />
          <Stat label="Failed tool calls" value={m.failed_tool_calls} hint={`of ${m.total_tool_calls} calls`} tone={m.failed_tool_calls ? "alert" : undefined} />
          <Stat label="Avg response" value={m.avg_response_latency_ms != null ? `${Math.round(m.avg_response_latency_ms)} ms` : "—"} hint={m.p95_response_latency_ms != null ? `p95 ${Math.round(m.p95_response_latency_ms)} ms` : undefined} />
          <Stat label="Refunds decided" value={m.refunds.approved + m.refunds.rejected} hint={`${m.refunds.approved} approved · ${m.refunds.rejected} rejected`} />
        </div>

        <section className="mt-6 rounded-xl border border-amber/30 bg-white">
          <div className="flex items-center justify-between border-b border-amber/20 bg-amber-soft/60 px-5 py-3">
            <h2 className="text-base font-semibold text-amber-ink">Refunds waiting for approval</h2>
            <span className="num rounded-full bg-amber px-2 py-0.5 text-xs font-semibold text-white">{pending.length}</span>
          </div>
          {pending.length === 0 ? <p className="px-5 py-6 text-sm text-ink/55">No refunds are waiting. New requests from VSR AI Assistant appear here and pause the customer's workflow until you decide.</p> : (
            <ul className="divide-y divide-line">{pending.map((r) => (
              <li key={r.refund_id} className="grid gap-4 px-5 py-4 md:grid-cols-[1fr_1fr_260px]">
                <div><div className="font-medium">{r.refund_id} <span className="font-normal text-ink/50">for {r.order_id}</span></div>
                  <div className="mt-0.5 text-sm text-ink/60">{r.customer} · {r.customer_email}</div>
                  <div className="mt-0.5 text-xs text-ink/45">Requested {day(r.created_at)} at {time(r.created_at)}</div></div>
                <div className="text-sm"><div className="num font-display text-lg font-semibold">{money(r.amount)} <span className="text-xs font-normal text-ink/45">of {money(r.order_total)}</span></div>
                  <div className="mt-0.5 text-ink/60">“{r.reason}”</div></div>
                <Decide r={r} onDone={load} />
              </li>))}</ul>
          )}
        </section>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <section className="panel p-5">
            <h2 className="text-base font-semibold">Agent usage</h2>
            <p className="text-xs text-ink/50">Executions per LangGraph node</p>
            {m.agent_usage.length === 0 ? <p className="py-10 text-sm text-ink/50">No agent runs yet. Start a chat as a customer.</p> : (
              <div className="mt-4 h-56"><ResponsiveContainer>
                <BarChart data={m.agent_usage.map((a) => ({ ...a, name: label(a.agent) }))} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <CartesianGrid horizontal={false} stroke="#E3E6EC" /><XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: "#64708a" }} />
                  <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 12, fill: "#131B2E" }} /><Tooltip cursor={{ fill: "#F5F6F8" }} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>{m.agent_usage.map((a) => <Cell key={a.agent} fill={AGENT_COLORS[a.agent] ?? "#64708a"} />)}</Bar>
                </BarChart></ResponsiveContainer></div>
            )}
          </section>
          <section className="panel p-5">
            <h2 className="text-base font-semibold">Customer intents</h2>
            <p className="text-xs text-ink/50">Supervisor routing decisions</p>
            {m.intent_distribution.length === 0 ? <p className="py-10 text-sm text-ink/50">No routed requests yet.</p> : (
              <div className="mt-4 h-56"><ResponsiveContainer>
                <BarChart data={m.intent_distribution.map((i) => ({ ...i, name: label(i.intent) }))} margin={{ bottom: 30 }}>
                  <CartesianGrid vertical={false} stroke="#E3E6EC" /><XAxis dataKey="name" interval={0} angle={-25} textAnchor="end" tick={{ fontSize: 11, fill: "#131B2E" }} height={50} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#64708a" }} width={30} /><Tooltip cursor={{ fill: "#F5F6F8" }} />
                  <Bar dataKey="count" fill="#0F766E" radius={[4, 4, 0, 0]} />
                </BarChart></ResponsiveContainer></div>
            )}
          </section>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          <section className="panel">
            <h2 className="border-b border-line px-5 py-3 text-base font-semibold">Tool calls</h2>
            <div className="overflow-x-auto"><table className="w-full text-sm">
              <thead className="text-left text-xs text-ink/50"><tr><th className="px-5 py-2 font-medium">Tool</th><th className="text-right font-medium">Calls</th><th className="px-5 text-right font-medium">Failures</th></tr></thead>
              <tbody className="divide-y divide-line">{m.tool_usage.map((t) => (
                <tr key={t.tool}><td className="px-5 py-2.5 font-mono text-[12.5px]">{t.tool}</td><td className="num text-right">{t.count}</td>
                  <td className={`num px-5 text-right ${t.failures ? "text-alert" : "text-ink/40"}`}>{t.failures}</td></tr>))}
                {m.tool_usage.length === 0 && <tr><td colSpan={3} className="px-5 py-6 text-ink/50">No tool calls recorded yet.</td></tr>}</tbody>
            </table></div>
          </section>
          <section className="panel">
            <h2 className="border-b border-line px-5 py-3 text-base font-semibold">Recent decisions</h2>
            <ul className="divide-y divide-line">{decided.map((r) => (
              <li key={r.refund_id} className="px-5 py-3 text-sm">
                <div className="flex items-center justify-between gap-2"><span className="font-medium">{r.refund_id} · {money(r.amount)}</span><Status value={r.status} /></div>
                <div className="mt-0.5 text-xs text-ink/50">{r.approved_by} · {day(r.decided_at)} {time(r.decided_at)}{r.simulated_transaction_id && <> · <span className="font-mono">{r.simulated_transaction_id}</span></>}</div>
              </li>))}
              {decided.length === 0 && <li className="px-5 py-6 text-sm text-ink/50">Approved and rejected refunds appear here with the approver and timestamp.</li>}</ul>
          </section>
        </div>

        {m.recent_failures.length > 0 && (
          <section className="panel mt-6">
            <h2 className="border-b border-line px-5 py-3 text-base font-semibold">Recent failures</h2>
            <ul className="divide-y divide-line text-sm">{m.recent_failures.map((f, i) => (
              <li key={i} className="flex flex-wrap gap-x-3 px-5 py-2.5"><span className="font-mono text-[12.5px]">{f.tool ?? f.agent}</span><span className="flex-1 text-ink/60">{f.error}</span><span className="text-xs text-ink/40">{day(f.at)} {time(f.at)}</span></li>))}</ul>
          </section>
        )}
      </>}
    </div>
  );
}
