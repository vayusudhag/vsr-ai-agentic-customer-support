import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Logo } from "../components/Logo";
import { ErrorNote } from "../components/ui";

type Demo = { label: string; email: string; password: string };

// Synthetic demo accounts are listed here so they appear instantly,
// even while the free-tier backend is still waking up.
const DEMOS: Demo[] = [
  { label: "Pardha Saradhi (customer)", email: "pardha.saradhi@example.com", password: "demo1234" },
  { label: "Pavan Y (customer)", email: "pavan.y@example.com", password: "demo1234" },
  { label: "Gopireddy VSR (admin)", email: "gopireddy.vsr@example.com", password: "admin1234" },
];

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
const WAKE_TIMEOUT_MS = 120_000; // Render free instances can take ~1 minute to start
const PING_INTERVAL_MS = 3_000;

type ServerState = "checking" | "waking" | "ready" | "down";

async function pingBackend(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/api/health`, { signal: AbortSignal.timeout(10_000), cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [server, setServer] = useState<ServerState>("checking");
  const [elapsed, setElapsed] = useState(0);

  const wake = useCallback(async (isCancelled: () => boolean) => {
    setServer("checking"); setElapsed(0);
    const start = Date.now();
    while (!isCancelled()) {
      if (await pingBackend()) { if (!isCancelled()) setServer("ready"); return; }
      const spent = Date.now() - start;
      if (isCancelled()) return;
      if (spent > WAKE_TIMEOUT_MS) { setServer("down"); return; }
      setServer("waking"); setElapsed(Math.round(spent / 1000));
      await new Promise((r) => setTimeout(r, PING_INTERVAL_MS));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    wake(() => cancelled);
    return () => { cancelled = true; };
  }, [wake]);

  const go = async (creds: Demo) => {
    setBusy(true); setErr("");
    try {
      const u = await login(creds.email, creds.password);
      nav(u.role === "admin" ? "/admin" : "/app/chat");
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };

  const ready = server === "ready";

  return (
    <div className="grid min-h-[100dvh] lg:grid-cols-[1fr_1.1fr]">
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Link to="/"><Logo /></Link>
        <div className="mx-auto my-auto w-full max-w-sm py-12">
          <h1 className="text-3xl font-semibold tracking-tight">
            Welcome to VSR AI
          </h1>
          <p className="mt-3 text-base text-ink/65">
            Choose an account to explore.
          </p>

          {server !== "ready" && (
            <div role="status" aria-live="polite" className="mt-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {server === "down" ? (
                <>
                  <p className="font-semibold">The demo server isn't responding yet.</p>
                  <p className="mt-1 text-amber-900/80">It may still be starting up. Please try again.</p>
                  <button type="button" onClick={() => wake(() => false)} className="mt-3 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700">
                    Try again
                  </button>
                </>
              ) : (
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-amber-600 border-t-transparent" aria-hidden="true" />
                  <div>
                    <p className="font-semibold">{server === "checking" ? "Connecting to the demo server…" : "Waking up the demo server…"}</p>
                    <p className="mt-1 text-amber-900/80">
                      This demo runs on a free hosting tier that sleeps when idle, so the first visit can take up to a minute.
                      {server === "waking" && elapsed > 0 && ` (${elapsed}s)`}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {err && <ErrorNote message={err} />}

          <div className="mt-8 space-y-3">
            {DEMOS.map((d) => {
              const isAdmin = d.label.toLowerCase().includes("admin");
              const name = d.label.replace(/\s*\((customer|admin)\)$/i, "");

              return (
                <button
                  key={d.email}
                  type="button"
                  onClick={() => go(d)}
                  disabled={busy || !ready}
                  className="group flex w-full items-center gap-4 rounded-xl border border-line bg-white px-5 py-4 text-left shadow-sm transition-all hover:border-teal-500 hover:bg-teal-50 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-500 disabled:opacity-50"
                >
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-teal-50 text-xl">
                    {isAdmin ? "🛡️" : "👤"}
                  </span>

                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-ink">{name}</span>
                    <span className="mt-1 block text-xs text-ink/50">
                      {isAdmin ? "Administrator" : "Customer"}
                    </span>
                  </span>

                  <span className="text-xl font-semibold text-teal-600 transition-transform group-hover:translate-x-1">
                    →
                  </span>
                </button>
              );
            })}
          </div>

          <p className="mt-6 text-center text-xs text-ink/45">
            Demo environment · Synthetic data only · No password required
          </p>
        </div>
      </div>
      <div className="relative hidden overflow-hidden bg-ink lg:block">
        <div className="absolute inset-0 opacity-[.07]" style={{ backgroundImage: "radial-gradient(#fff 1px, transparent 1px)", backgroundSize: "22px 22px" }} />
        <div className="relative flex h-full flex-col justify-center px-12 py-12 text-white xl:px-16">
          <div className="max-w-lg">
            <div className="mb-5 text-xs font-semibold uppercase tracking-[0.22em] text-teal-300">
              Inside VSR AI
            </div>
            <h2 className="font-display text-3xl font-semibold leading-tight xl:text-4xl">
              How VSR AI Works
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-white/60">
              Five specialized AI agents work together to deliver accurate,
              transparent customer support.
            </p>

            <div className="mt-9 space-y-6">
              {[
                ["01", "Understand the request", "The Supervisor identifies the customer's intent and selects the appropriate agents."],
                ["02", "Route to specialists", "Orders, Returns, Knowledge, and Product agents handle their respective tasks."],
                ["03", "Retrieve trusted information", "Agents use approved tools to access customer orders, product data, and company policies."],
                ["04", "Deliver a grounded response", "Customers receive answers with visible agent activity and policy citations when relevant."],
                ["05", "Human approval for refunds", "Refund requests requiring approval are reviewed by an administrator before processing."]
              ].map(([number, title, description]) => (
                <div key={number} className="flex gap-4 border-b border-white/10 pb-5 last:border-0">
                  <span className="shrink-0 font-mono text-sm font-semibold text-teal-300">{number}</span>
                  <div>
                    <h3 className="text-base font-semibold">{title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-white/55">{description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
