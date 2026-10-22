import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageSquare, Truck } from "lucide-react";
import { api, money } from "../lib/api";
import { ErrorNote, Loading, PageHeader, Status } from "../components/ui";

type Order = {
  order_id: string; status: string; carrier: string | null; tracking_number: string | null; placed_on: string; total: number;
  estimated_delivery: string | null; delivered_on: string | null; shipping_address: string;
  items: { name: string; quantity: number; unit_price: number; returnable: boolean }[];
  return_eligibility: { eligible: boolean; reasons: string[]; days_remaining: number | null };
};

export default function Orders() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [err, setErr] = useState("");
  const nav = useNavigate();
  const load = () => { setErr(""); api<Order[]>("/api/orders").then(setOrders).catch((e) => setErr(e.message)); };
  useEffect(load, []);
  const ask = (prompt: string) => nav("/app/chat", { state: { prompt } });

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-8">
      <PageHeader title="My orders" sub="Live from the order database. Ask VSR AI Assistant about any order for tracking, returns or refunds." />
      {err && <ErrorNote message={err} onRetry={load} />}
      {!orders && !err && <Loading label="Loading your orders" />}
      {orders?.length === 0 && <p className="text-sm text-ink/55">No orders yet. Browse the product catalog to get started.</p>}
      <div className="space-y-3">
        {orders?.map((o) => (
          <article key={o.order_id} className="panel overflow-hidden">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line px-5 py-3.5">
              <span className="font-display font-semibold">{o.order_id}</span><Status value={o.status} />
              <span className="text-sm text-ink/55">Placed {o.placed_on}</span>
              <span className="num ml-auto font-medium">{money(o.total)}</span>
            </div>
            <div className="grid gap-5 px-5 py-4 md:grid-cols-[1.3fr_1fr]">
              <ul className="space-y-1.5 text-sm">
                {o.items.map((i) => (
                  <li key={i.name} className="flex justify-between gap-4">
                    <span>{i.quantity} × {i.name}{!i.returnable && <span className="ml-2 text-xs text-amber-ink">final sale</span>}</span>
                    <span className="num text-ink/55">{money(i.unit_price)}</span>
                  </li>
                ))}
              </ul>
              <div className="space-y-1.5 text-sm text-ink/70">
                {o.carrier && <div className="flex items-center gap-2"><Truck className="h-4 w-4 text-ink/40" />{o.carrier} · <span className="font-mono text-xs">{o.tracking_number}</span></div>}
                {o.estimated_delivery && <div>Expected {o.estimated_delivery}</div>}
                {o.delivered_on && <div>Delivered {o.delivered_on}</div>}
                <div className={o.return_eligibility.eligible ? "text-lagoon-ink" : "text-ink/50"}>
                  {o.return_eligibility.eligible ? `Returnable for ${o.return_eligibility.days_remaining} more days` : "Not returnable right now"}
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 border-t border-line bg-paper/60 px-5 py-2.5">
              <button className="btn-ghost px-2.5 py-1.5 text-[13px]" onClick={() => ask(`Where is my order ${o.order_id}?`)}><MessageSquare className="h-3.5 w-3.5" />Ask about this order</button>
              {o.return_eligibility.eligible && <button className="btn-ghost px-2.5 py-1.5 text-[13px]" onClick={() => ask(`Can I return ${o.order_id}?`)}>Check return options</button>}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
