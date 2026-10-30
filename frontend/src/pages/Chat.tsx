import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useLocation } from "react-router-dom";
import { ArrowUp, BookOpen, Clock3, History, Plus, Trash2, UserCheck } from "lucide-react";
import { api, day, money, time, type ChatMessage, type ConversationSummary, type Citation } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Markdown } from "../components/Markdown";
import { RouteStrip } from "../components/RouteStrip";
import { LogoMark } from "../components/Logo";
import { ErrorNote } from "../components/ui";

const COMMON_STARTERS = [
  "Recommend noise-cancelling headphones under $300",
  "Do you ship to Canada?",
  "Show me all my orders",
];

// Each demo customer owns different orders, so the suggestions use that customer's own order ids.
const STARTERS_BY_EMAIL: Record<string, string[]> = {
  "pardha.saradhi@example.com": [
    "Where is my order ORD-1001?",
    "Can I return ORD-1002?",
    "I want a refund for ORD-1002, the strap broke",
  ],
  "pavan.y@example.com": [
    "Where is my order ORD-1007?",
    "Can I return ORD-1006?",
    "I want a refund for ORD-1006, the chair arrived damaged",
  ],
};

const startersFor = (email?: string) => [
  ...((email && STARTERS_BY_EMAIL[email]) || []),
  ...COMMON_STARTERS,
];

function Sources({ cites }: { cites: Citation[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(!open)} className="inline-flex items-center gap-1.5 text-xs font-medium text-lagoon-ink hover:underline">
        <BookOpen className="h-3.5 w-3.5" />{cites.length} policy source{cites.length > 1 ? "s" : ""}
      </button>
      {open && (
        <ol className="mt-2 space-y-2">
          {cites.map((c) => (
            <li key={c.chunk_id} className="rounded-lg border border-line bg-paper px-3 py-2 text-xs">
              <div className="font-medium"><span className="mr-1.5 rounded bg-lagoon-soft px-1 text-lagoon-ink">{c.n}</span>{c.doc_title} › {c.section}
                <span className="num ml-2 font-normal text-ink/40">similarity {c.score.toFixed(2)}</span></div>
              <p className="mt-1 text-ink/60">{c.excerpt}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Bubble({ m, decided }: { m: ChatMessage; decided?: string }) {
  if (m.role === "user")
    return (
      <div className="flex flex-col items-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-[15px] text-white sm:max-w-[70%]">{m.content}</div>
        <span className="mt-1 text-[11px] text-ink/40">{time(m.created_at)}</span>
      </div>
    );
  const pending = m.meta.pending_refund;
  const decision = m.meta.event?.startsWith("refund_");
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 shrink-0"><LogoMark size={28} /></div>
      <div className="min-w-0 max-w-[92%] text-[15px] sm:max-w-[80%]">
        {decision && (
          <div className="mb-1.5 inline-flex items-center gap-1.5 rounded-full bg-lagoon-soft px-2 py-0.5 text-[11.5px] font-medium text-lagoon-ink">
            <UserCheck className="h-3 w-3" />Decision from VSR support team
          </div>
        )}
        <Markdown text={m.content} />
        {pending && !decided && (
          <div className="mt-3 flex items-center gap-3 rounded-lg border border-amber/30 bg-amber-soft px-3 py-2.5 text-sm text-amber-ink">
            <Clock3 className="h-4 w-4 shrink-0" />
            <span><strong className="font-semibold">{pending.refund_id}</strong> · {money(pending.amount)} is waiting for admin approval. This conversation updates automatically.</span>
          </div>
        )}
        {pending && decided && (
          <div className="mt-3 flex items-center gap-3 rounded-lg border border-line bg-paper px-3 py-2.5 text-sm text-ink/70">
            <UserCheck className="h-4 w-4 shrink-0" />
            <span><strong className="font-semibold">{pending.refund_id}</strong> · {money(pending.amount)} was {decided} by the support team (see below).</span>
          </div>
        )}
        {!!m.meta.citations?.length && <Sources cites={m.meta.citations} />}
        <RouteStrip meta={m.meta} />
        <div className="mt-1 text-[11px] text-ink/40">{time(m.created_at)}</div>
      </div>
    </div>
  );
}

export default function Chat() {
  const { user } = useAuth();
  const loc = useLocation() as { state?: { prompt?: string } };
  const [convs, setConvs] = useState<ConversationSummary[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState(loc.state?.prompt ?? "");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState("");
  const [showList, setShowList] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const loadConvs = useCallback(() => api<ConversationSummary[]>("/api/chat/conversations").then(setConvs).catch((e) => setErr(e.message)), []);
  const openConv = useCallback(async (id: string) => {
    setErr(""); setActive(id); setShowList(false);
    try { setMessages((await api<{ messages: ChatMessage[] }>(`/api/chat/conversations/${id}`)).messages); }
    catch (e) { setErr((e as Error).message); }
  }, []);
  useEffect(() => { loadConvs(); }, [loadConvs]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, sending]);

  // Poll while a refund in this conversation awaits a human decision.
  const awaiting = messages.some((m) => m.meta.pending_refund) &&
    !messages.some((m) => m.meta.event?.startsWith("refund_") && m.id > Math.max(...messages.filter((x) => x.meta.pending_refund).map((x) => x.id)));
  useEffect(() => {
    if (!active || !awaiting) return;
    const t = setInterval(() => openConv(active), 5000);
    return () => clearInterval(t);
  }, [active, awaiting, openConv]);

  const send = async (text: string) => {
    const msg = text.trim();
    if (!msg || sending) return;
    setErr(""); setInput(""); setSending(true);
    const optimistic: ChatMessage = { id: Date.now(), role: "user", content: msg, meta: {}, created_at: new Date().toISOString() };
    setMessages((m) => [...m, optimistic]);
    try {
      const r = await api<{ conversation_id: string; message: ChatMessage }>("/api/chat", { method: "POST", body: JSON.stringify({ message: msg, conversation_id: active }) });
      setActive(r.conversation_id);
      setMessages((m) => [...m, r.message]);
      loadConvs();
    } catch (e) {
      setMessages((m) => m.filter((x) => x.id !== optimistic.id)); setInput(msg); setErr((e as Error).message);
    } finally { setSending(false); }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); send(input); };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } };
  const remove = async (id: string) => {
    await api(`/api/chat/conversations/${id}`, { method: "DELETE" }).catch(() => {});
    if (id === active) { setActive(null); setMessages([]); }
    loadConvs();
  };

  const list = (
    <div className="flex h-full flex-col">
      <div className="p-3"><button className="btn-outline w-full" onClick={() => { setActive(null); setMessages([]); setShowList(false); }}><Plus className="h-4 w-4" />New conversation</button></div>
      <div className="px-4 pb-2 text-xs font-medium text-ink/45">History</div>
      <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
        {convs.length === 0 && <p className="px-3 text-sm text-ink/45">Your conversations will appear here.</p>}
        {convs.map((c) => (
          <div key={c.id} className={`group flex items-center rounded-lg ${c.id === active ? "bg-ink/[.06]" : "hover:bg-ink/[.03]"}`}>
            <button onClick={() => openConv(c.id)} className="min-w-0 flex-1 px-3 py-2 text-left">
              <div className="truncate text-sm">{c.title}</div>
              <div className="text-[11px] text-ink/40">{day(c.updated_at)} · {c.message_count} messages</div>
            </button>
            <button onClick={() => remove(c.id)} className="mr-1 rounded p-1.5 text-ink/30 opacity-0 hover:text-alert group-hover:opacity-100 focus:opacity-100" aria-label="Delete conversation"><Trash2 className="h-3.5 w-3.5" /></button>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="flex h-full">
      <aside className="hidden w-64 shrink-0 border-r border-line bg-white md:block">{list}</aside>
      {showList && <div className="fixed inset-0 z-30 md:hidden"><div className="absolute inset-0 bg-ink/30" onClick={() => setShowList(false)} /><div className="absolute inset-y-0 left-0 w-72 bg-white">{list}</div></div>}

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-line bg-white/70 px-4 py-3 backdrop-blur sm:px-6">
          <div className="flex items-center gap-2">
            <button className="btn-ghost -ml-2 px-2 md:hidden" onClick={() => setShowList(true)} aria-label="Conversation history"><History className="h-4 w-4" /></button>
            <div><div className="font-display text-[15px] font-semibold">VSR AI Assistant</div>
              <div className="text-xs text-ink/50">Orders, returns, refunds, policies and products</div></div>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6">
            {messages.length === 0 && !sending && (
              <div className="pt-8 sm:pt-16">
                <LogoMark size={40} />
                <h2 className="mt-5 text-2xl font-semibold">Hi {user?.full_name.split(" ")[0]}, what can I help with?</h2>
                <p className="mt-1.5 text-sm text-ink/55">I can only see orders on your account. Refunds are reviewed by a person before they're issued.</p>
                <div className="mt-8 grid gap-2 sm:grid-cols-2">
                  {startersFor(user?.email).map((s) => (
                    <button key={s} onClick={() => send(s)} className="rounded-lg border border-line bg-white px-4 py-3 text-left text-sm text-ink/80 transition-colors hover:border-lagoon/40 hover:bg-lagoon-soft/40">{s}</button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m) => {
              const decision = m.meta.pending_refund && messages.find((x) => x.id > m.id && x.meta.event?.startsWith("refund_") && x.content.includes(m.meta.pending_refund!.refund_id));
              return <Bubble key={m.id} m={m} decided={decision ? decision.meta.event!.replace("refund_", "") : undefined} />;
            })}
            {sending && (
              <div className="flex items-center gap-3" aria-live="polite">
                <LogoMark size={28} />
                <div className="typing flex gap-1 rounded-full bg-white px-3 py-2.5 shadow-sm ring-1 ring-line"><span className="h-1.5 w-1.5 rounded-full bg-ink/60" /><span className="h-1.5 w-1.5 rounded-full bg-ink/60" /><span className="h-1.5 w-1.5 rounded-full bg-ink/60" /></div>
                <span className="text-xs text-ink/45">Routing to the right agent</span>
              </div>
            )}
            {err && <ErrorNote message={err} />}
            <div ref={endRef} />
          </div>
        </div>

        <form onSubmit={submit} className="border-t border-line bg-white px-4 py-3 sm:px-6">
          <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-xl border border-line bg-paper px-3 py-2 focus-within:border-lagoon focus-within:ring-2 focus-within:ring-lagoon/15">
            <label htmlFor="msg" className="sr-only">Message VSR AI Assistant</label>
            <textarea id="msg" rows={1} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} maxLength={2000}
              placeholder="Ask about an order, a return, or a product" className="max-h-40 min-h-[24px] flex-1 resize-none bg-transparent py-1.5 text-[15px] outline-none placeholder:text-ink/40 focus-visible:ring-0 focus-visible:ring-offset-0" />
            <button className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-lagoon text-white transition-colors hover:bg-lagoon-600 disabled:bg-ink/20" disabled={!input.trim() || sending} aria-label="Send message">
              <ArrowUp className="h-4 w-4" /></button>
          </div>
          <p className="mx-auto mt-1.5 max-w-3xl text-[11px] text-ink/40">Synthetic demo data. Refunds are simulated; no real payments are made.</p>
        </form>
      </section>
    </div>
  );
}
