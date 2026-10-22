import { useEffect, useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { api, day, money } from "../lib/api";
import { ErrorNote, Loading, PageHeader, Status } from "../components/ui";

type Data = {
  returns: { rma_number: string; order_id: string; reason: string; status: string; created_at: string }[];
  refunds: { refund_id: string; order_id: string; amount: number; status: string; requested_on: string; decided_on: string | null }[];
};
type Order = { order_id: string; return_eligibility: { eligible: boolean; days_remaining: number | null } };

export default function Returns() {
  const [data, setData] = useState<Data | null>(null);
  const [eligible, setEligible] = useState<Order[]>([]);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ order_id: "", reason: "" });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState("");
  const load = () => {
    setErr("");
    api<Data>("/api/returns").then(setData).catch((e) => setErr(e.message));
    api<Order[]>("/api/orders").then((o) => setEligible(o.filter((x) => x.return_eligibility.eligible))).catch(() => {});
  };
  useEffect(load, []);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(""); setDone("");
    try {
      const r = await api<{ rma_number: string }>("/api/returns", { method: "POST", body: JSON.stringify(form) });
      setDone(`Return ${r.rma_number} created for ${form.order_id}.`); setForm({ order_id: "", reason: "" }); load();
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-8">
      <PageHeader title="Returns & refunds" sub="Returns get an RMA immediately. Refunds are reviewed by the VSR support team, and the decision is posted in your chat." />
      {err && <div className="mb-4"><ErrorNote message={err} /></div>}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <section className="panel">
            <h2 className="border-b border-line px-5 py-3 text-base font-semibold">Refund requests</h2>
            {!data ? <div className="px-5"><Loading /></div> : data.refunds.length === 0 ? (
              <p className="px-5 py-6 text-sm text-ink/55">No refund requests. Ask VSR AI Assistant to request one for an eligible order.</p>
            ) : (
              <div className="overflow-x-auto"><table className="w-full text-sm">
                <thead className="text-left text-xs text-ink/50"><tr><th className="px-5 py-2 font-medium">Refund</th><th className="font-medium">Order</th><th className="font-medium">Amount</th><th className="font-medium">Status</th><th className="px-5 font-medium">Requested</th></tr></thead>
                <tbody className="divide-y divide-line">{data.refunds.map((r) => (
                  <tr key={r.refund_id}><td className="px-5 py-3 font-medium">{r.refund_id}</td><td>{r.order_id}</td><td className="num">{money(r.amount)}</td>
                    <td><Status value={r.status} /></td><td className="px-5 text-ink/55">{r.requested_on}</td></tr>))}</tbody>
              </table></div>
            )}
          </section>
          <section className="panel">
            <h2 className="border-b border-line px-5 py-3 text-base font-semibold">Returns</h2>
            {data && data.returns.length === 0 && <p className="px-5 py-6 text-sm text-ink/55">No returns started yet.</p>}
            <ul className="divide-y divide-line">{data?.returns.map((r) => (
              <li key={r.rma_number} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3 text-sm">
                <span className="font-medium">{r.rma_number}</span><span className="text-ink/55">{r.order_id}</span><Status value={r.status} />
                <span className="w-full text-ink/55 sm:w-auto sm:flex-1 sm:text-right">{r.reason} · {day(r.created_at)}</span></li>))}</ul>
          </section>
        </div>
        <form onSubmit={submit} className="panel h-fit space-y-4 p-5">
          <h2 className="text-base font-semibold">Start a return</h2>
          {eligible.length === 0 ? <p className="text-sm text-ink/55">None of your orders are eligible for return right now.</p> : <>
            <label className="block text-sm font-medium">Order
              <select className="input mt-1.5" value={form.order_id} onChange={(e) => setForm({ ...form, order_id: e.target.value })} required>
                <option value="">Choose an eligible order</option>
                {eligible.map((o) => <option key={o.order_id} value={o.order_id}>{o.order_id} ({o.return_eligibility.days_remaining} days left)</option>)}
              </select></label>
            <label className="block text-sm font-medium">Reason
              <input className="input mt-1.5" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} minLength={3} maxLength={255} required placeholder="e.g. Doesn't fit" /></label>
            <button className="btn-primary w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}Start return</button>
          </>}
          {done && <p className="text-sm text-lagoon-ink">{done}</p>}
        </form>
      </div>
    </div>
  );
}
