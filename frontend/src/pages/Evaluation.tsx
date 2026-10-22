import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, day } from "../lib/api";
import { ErrorNote, Loading, PageHeader } from "../components/ui";

type AnyObj = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
type History = { version: string; description: string; run_at: string; routing_dev: number; routing_heldout: number | null; tool_selection: number;
  task_completion: number; precision_at_5: number; answered_rate: number | null; abstention_dev: number | null; abstention_heldout_v1: number | null;
  abstention_heldout_v2: number | null; answered_heldout_v2: number | null; latency_p50_ms: number };
type Results = { available: boolean; message?: string; run_at: string; version?: string; results_mode?: string; conditions: AnyObj; metrics: AnyObj;
  baseline?: AnyObj | null; history?: History[]; llm?: AnyObj | null; llm_status?: string };

const pct = (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);

function Metric({ title, value, n, method, children, note }: { title: string; value: string; n: number | string; method: string; children?: React.ReactNode; note?: string }) {
  return (
    <section className="panel flex flex-col p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[15px] font-semibold">{title}</h3><span className="num text-xs text-ink/45">n = {n}</span>
      </div>
      <div className="num mt-2 font-display text-[34px] font-semibold leading-none">{value}</div>
      {children && <div className="mt-3 space-y-1 text-sm text-ink/70">{children}</div>}
      <p className="mt-4 border-t border-line pt-3 text-xs leading-relaxed text-ink/50">{method}</p>
      {note && <p className="mt-2 text-xs leading-relaxed text-amber-ink">{note}</p>}
    </section>
  );
}
const Row = ({ k, v }: { k: string; v: string }) => <div className="flex justify-between gap-4"><span className="text-ink/55">{k}</span><span className="num font-medium">{v}</span></div>;

export default function Evaluation() {
  const [r, setR] = useState<Results | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<Results>("/api/evaluation/results").then(setR).catch((e) => setErr(e.message)); }, []);
  if (err) return <div className="p-8"><ErrorNote message={err} /></div>;
  if (!r) return <div className="px-8"><Loading label="Loading evaluation results" /></div>;
  if (!r.available) return <div className="mx-auto max-w-3xl p-8"><PageHeader title="AI evaluation" /><p className="text-sm text-ink/60">{r.message}</p></div>;
  const M = r.metrics, c = r.conditions, b = r.baseline?.metrics;
  const perIntent = Object.entries(M.routing.per_intent as Record<string, number>).map(([k, v]) => ({ name: k.replace(/_/g, " "), acc: Math.round(v * 100) }));

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
      <PageHeader title="AI evaluation" sub="Results from the last run of backend/eval/run_eval.py. Nothing on this page is typed in by hand; it reads eval/results/*.json."
        actions={<span className="rounded-full bg-ink px-3 py-1 text-xs font-medium text-white">{r.version ?? "latest"} · {r.results_mode ?? c.agent_mode} results</span>} />
      <div className="mb-6 grid gap-px overflow-hidden rounded-xl border border-line bg-line md:grid-cols-2">
        <div className="bg-white px-5 py-4">
          <div className="flex items-center gap-2 text-sm font-semibold"><span className="h-2 w-2 rounded-full bg-lagoon" />Deterministic workflows</div>
          <p className="mt-1 text-sm text-ink/60">Rule-based routing, policy-driven tool calls, extractive answers. Every number on this page comes from this mode.</p>
        </div>
        <div className="bg-white px-5 py-4">
          <div className="flex items-center gap-2 text-sm font-semibold"><span className="h-2 w-2 rounded-full bg-ink/25" />LLM-powered workflows</div>
          <p className="mt-1 text-sm text-ink/60">{r.llm ? "Evaluated: see latest_llm.json." : r.llm_status}</p>
        </div>
      </div>
      <div className="mb-6 rounded-xl border border-line bg-white px-5 py-4 text-sm">
        <div className="flex flex-wrap gap-x-8 gap-y-1.5">
          <Row k="Run" v={`${day(r.run_at)} ${new Date(r.run_at).getFullYear()}`} /><Row k="Agent mode" v={c.agent_mode} /><Row k="Embeddings" v={c.embedder} />
          <Row k="Database" v={c.database} /><Row k="Chunks indexed" v={String(c.chunks_indexed)} /><Row k="Python" v={c.python} />
        </div>
        <p className="mt-3 text-xs leading-relaxed text-ink/50">{c.note}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Metric title="Intent routing accuracy" value={pct(M.routing.heldout?.value)} n={`${M.routing.heldout?.n} held-out`} method={M.routing.method}
          note="Headline uses the held-out set. The dev set was used to revise rules once, so its score is optimistic.">
          <Row k={`Dev set (n=${M.routing.n})`} v={pct(M.routing.value)} />{b && <Row k="Dev set, baseline run" v={pct(b.routing.value)} />}
        </Metric>
        <Metric title="Tool-selection accuracy" value={pct(M.tool_selection.value)} n={M.tool_selection.n} method={M.tool_selection.method}>
          <Row k="Tool-call precision" v={pct(M.tool_selection.tool_call_precision)} /><Row k="Tool-call recall" v={pct(M.tool_selection.tool_call_recall)} />
          {b && <Row k="Baseline run" v={pct(b.tool_selection.value)} />}
        </Metric>
        <Metric title="Task completion rate" value={pct(M.task_completion.value)} n={M.task_completion.n} method={M.task_completion.method} />
        <Metric title="Retrieval Precision@5" value={M.retrieval.value.toFixed(3)} n={M.retrieval.n} method={M.retrieval.method}
          note={`With 1–2 relevant sections per query, the best possible Precision@5 on this set is ${M.retrieval.ceiling.toFixed(2)}.`}>
          <Row k="Recall@5" v={pct(M.retrieval.recall_at_5)} /><Row k="Hit@1" v={pct(M.retrieval.hit_at_1)} /><Row k="MRR" v={M.retrieval.mrr.toFixed(3)} />
        </Metric>
        <Metric title="Answer groundedness" value={pct(M.groundedness.value)} n={`${M.groundedness.n_kb_answers} answers`} method={M.groundedness.method}>
          <Row k="Cites a relevant section" v={pct(M.groundedness.relevant_citation_rate)} />
          <Row k="Answer rate, answerable dev (n=30)" v={pct(M.groundedness.answered_rate)} />
          <div className="pt-1"><span className="rounded bg-ink/5 px-1.5 py-0.5 text-xs font-medium text-ink/60">LLM-as-judge: Not Evaluated</span></div>
        </Metric>
        {M.groundedness.heldout_v2 && (
          <Metric title="Abstention on unanswerable questions" value={pct(M.groundedness.heldout_v2.abstention_accuracy)}
            n={`${M.groundedness.heldout_v2.n_unanswerable} held-out`} method={M.groundedness.abstention_definition ?? ""}
            note="Headline uses the fresh v2 held-out set, written before the v3 gate was built. The v1 held-out set was inspected while designing the gate, so it is shown as seen.">
            <Row k={`Answered, held-out answerable (n=${M.groundedness.heldout_v2.n_answerable})`} v={pct(M.groundedness.heldout_v2.answered_rate)} />
            <Row k={`Dev unanswerable (n=${M.groundedness.n_unanswerable})`} v={pct(M.groundedness.abstention_accuracy_unanswerable)} />
            <Row k={`v1 held-out, seen (n=${M.groundedness.n_unanswerable_heldout})`} v={pct(M.groundedness.abstention_accuracy_heldout)} />
          </Metric>
        )}
        <Metric title="API latency (p50)" value={`${Math.round(M.latency.api_ms.p50)} ms`} n={M.latency.n} method={M.latency.method}>
          <Row k="p95 (API)" v={`${Math.round(M.latency.api_ms.p95)} ms`} /><Row k="Mean graph execution" v={`${Math.round(M.latency.graph_ms.mean)} ms`} />
        </Metric>
      </div>

      {!!r.history?.length && (
        <section className="panel mt-6">
          <h2 className="border-b border-line px-5 py-3 text-base font-semibold">Run history (deterministic mode)</h2>
          <div className="overflow-x-auto"><table className="w-full whitespace-nowrap text-sm">
            <thead className="text-left text-xs text-ink/50"><tr>
              {["Version", "Routing dev", "Routing held-out", "Tools", "Tasks", "P@5", "Answer rate", "Abstain dev", "Abstain held-out v2", "Answered held-out v2", "p50"].map((h) =>
                <th key={h} className="px-4 py-2 font-medium first:pl-5">{h}</th>)}</tr></thead>
            <tbody className="num divide-y divide-line">{r.history.map((h) => (
              <tr key={h.version}>
                <td className="py-2.5 pl-5 pr-4"><div className="font-medium">{h.version}</div><div className="text-xs text-ink/45">{h.description}</div></td>
                <td className="px-4">{pct(h.routing_dev)}</td><td className="px-4">{pct(h.routing_heldout)}</td><td className="px-4">{pct(h.tool_selection)}</td>
                <td className="px-4">{pct(h.task_completion)}</td><td className="px-4">{h.precision_at_5.toFixed(3)}</td><td className="px-4">{pct(h.answered_rate)}</td>
                <td className="px-4">{pct(h.abstention_dev)}</td><td className="px-4">{pct(h.abstention_heldout_v2)}</td><td className="px-4">{pct(h.answered_heldout_v2)}</td>
                <td className="px-4">{Math.round(h.latency_p50_ms)} ms</td>
              </tr>))}</tbody>
          </table></div>
          <p className="border-t border-line px-5 py-2.5 text-xs text-ink/50">— means the dataset did not exist yet for that run. v1 counted only the knowledge agent's refusal as abstention; v2 onward also counts the product agent's "no matching products".</p>
        </section>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="panel p-5">
          <h2 className="text-base font-semibold">Routing accuracy by intent (dev set)</h2>
          <div className="mt-4 h-64"><ResponsiveContainer>
            <BarChart data={perIntent} margin={{ bottom: 40 }}><CartesianGrid vertical={false} stroke="#E3E6EC" />
              <XAxis dataKey="name" interval={0} angle={-30} textAnchor="end" tick={{ fontSize: 11, fill: "#131B2E" }} height={60} />
              <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12, fill: "#64708a" }} width={44} /><Tooltip formatter={(v) => `${v}%`} cursor={{ fill: "#F5F6F8" }} />
              <Bar dataKey="acc" fill="#0F766E" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
        </section>
        <section className="panel">
          <h2 className="border-b border-line px-5 py-3 text-base font-semibold">Known failures in this run</h2>
          <ul className="divide-y divide-line text-sm">
            {[...(M.routing.heldout?.failures ?? []).map((f: AnyObj) => ({ k: "Routing (held-out)", t: f.text, d: `expected ${f.expected}, got ${f.predicted}` })),
              ...M.routing.failures.map((f: AnyObj) => ({ k: "Routing (dev)", t: f.text, d: `expected ${f.expected}, got ${f.predicted}` })),
              ...M.tool_selection.failures.map((f: AnyObj) => ({ k: "Tool selection", t: f.text, d: `expected ${f.expected}, called ${f.called}` })),
              ...M.task_completion.failures.map((f: AnyObj) => ({ k: "Task", t: f.name, d: f.notes }))].map((f, i) => (
              <li key={i} className="px-5 py-3"><div className="text-xs text-ink/45">{f.k}</div><div className="font-medium">{f.t}</div><div className="text-ink/55">{f.d}</div></li>))}
            {M.groundedness.heldout_v2 && M.groundedness.heldout_v2.abstention_accuracy < 1 && <li className="px-5 py-3"><div className="text-xs text-ink/45">Abstention (held-out v2)</div>
              <div className="text-ink/60">{Math.round((1 - M.groundedness.heldout_v2.abstention_accuracy) * M.groundedness.heldout_v2.n_unanswerable)} of {M.groundedness.heldout_v2.n_unanswerable} out-of-scope questions received loosely related policy sentences instead of a refusal. See abstention_details.csv.</div></li>}
            {M.groundedness.heldout_v2 && M.groundedness.heldout_v2.answered_rate < 1 && <li className="px-5 py-3"><div className="text-xs text-ink/45">Answer rate (held-out v2)</div>
              <div className="text-ink/60">Some answerable policy questions were routed to another agent instead of the knowledge agent. See answerable_heldout_v2_details.csv.</div></li>}
          </ul>
        </section>
      </div>
    </div>
  );
}
