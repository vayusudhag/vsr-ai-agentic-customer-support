import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Star } from "lucide-react";
import { api, money } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ErrorNote, Loading, PageHeader } from "../components/ui";

type Product = { sku: string; name: string; category: string; price: number; rating: number; stock: number; description: string; tags: string[]; returnable: boolean };

export default function Products() {
  const [all, setAll] = useState<Product[] | null>(null);
  const [err, setErr] = useState("");
  const [cat, setCat] = useState("All");
  const [q, setQ] = useState("");
  const { user } = useAuth();
  const nav = useNavigate();
  useEffect(() => { api<Product[]>("/api/products").then(setAll).catch((e) => setErr(e.message)); }, []);
  const cats = useMemo(() => ["All", ...Array.from(new Set(all?.map((p) => p.category)))], [all]);
  const shown = (all ?? []).filter((p) => (cat === "All" || p.category === cat) &&
    (!q || `${p.name} ${p.description} ${p.tags.join(" ")}`.toLowerCase().includes(q.toLowerCase())));

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
      <PageHeader title="Product catalog" sub={`${all?.length ?? "–"} products in the VSR Store demo catalog. The Products agent searches this same data.`}
        actions={<div className="relative w-full sm:w-72"><Search className="absolute left-3 top-2.5 h-4 w-4 text-ink/40" /><input className="input pl-9" placeholder="Filter products" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter products" /></div>} />
      <div className="mb-6 flex flex-wrap gap-1.5">
        {cats.map((c) => <button key={c} onClick={() => setCat(c)} className={`rounded-full px-3 py-1 text-sm transition-colors ${cat === c ? "bg-ink text-white" : "bg-white text-ink/70 ring-1 ring-line hover:ring-ink/25"}`}>{c}</button>)}
      </div>
      {err && <ErrorNote message={err} />}
      {!all && !err && <Loading label="Loading catalog" />}
      {all && shown.length === 0 && <p className="text-sm text-ink/55">No products match “{q}”. Clear the filter or pick another category.</p>}
      <div className="grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
        {shown.map((p) => (
          <article key={p.sku} className="flex flex-col bg-white p-5">
            <div className="flex items-start justify-between gap-3">
              <div><div className="text-xs text-ink/45">{p.category}</div><h3 className="mt-0.5 font-display text-[15px] font-semibold leading-snug">{p.name}</h3></div>
              <div className="num shrink-0 font-display font-semibold">{money(p.price)}</div>
            </div>
            <p className="mt-2 flex-1 text-sm leading-relaxed text-ink/60">{p.description}</p>
            <div className="mt-4 flex items-center justify-between text-xs text-ink/55">
              <span className="inline-flex items-center gap-1"><Star className="h-3.5 w-3.5 fill-amber text-amber" />{p.rating.toFixed(1)}</span>
              <span>{p.returnable ? `${p.stock} in stock` : "Final sale"}</span>
              {user?.role === "customer" && <button className="font-medium text-lagoon-ink hover:underline" onClick={() => nav("/app/chat", { state: { prompt: `Tell me about the ${p.name}. Is it a good pick?` } })}>Ask VSR AI</button>}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
