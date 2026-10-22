import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Logo } from "../components/Logo";
import { ErrorNote } from "../components/ui";

type Demo = { label: string; email: string; password: string };

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [demos, setDemos] = useState<Demo[]>([]);
  useEffect(() => { api<Demo[]>("/api/auth/demo-accounts").then(setDemos).catch(() => {}); }, []);

  const go = async (creds: Demo) => {
    setBusy(true); setErr("");
    try {
      const u = await login(creds.email, creds.password);
      nav(u.role === "admin" ? "/admin" : "/app/chat");
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };

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

          {err && <ErrorNote message={err} />}

          <div className="mt-8 space-y-3">
            {demos.map((d) => {
              const isAdmin = d.label.toLowerCase().includes("admin");
              const name = d.label.replace(/\\s*\\((customer|admin)\\)$/i, "");

              return (
                <button
                  key={d.email}
                  type="button"
                  onClick={() => go(d)}
                  disabled={busy}
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
