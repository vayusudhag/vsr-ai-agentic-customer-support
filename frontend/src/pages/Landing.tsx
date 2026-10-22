import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Logo } from "../components/Logo";

export default function Landing() {
  return (
    <div className="flex min-h-[100dvh] flex-col bg-paper">
      <header className="mx-auto flex w-full max-w-6xl items-center px-6 py-6">
        <Logo />
      </header>

      <main className="flex flex-1 items-center justify-center px-6 pb-20">
        <div className="mx-auto max-w-3xl text-center">
          <div className="mb-8 inline-flex flex-col items-center rounded-2xl border border-line bg-white px-7 py-3 text-xs font-medium tracking-[0.15em] uppercase">
            <span className="text-ink/70">Intelligent Customer Support</span>
            <span className="mt-1 text-teal-700">Powered by AI Agents</span>
          </div>

          <div className="flex justify-center">
            <div className="origin-center scale-[3] my-12">
              <Logo />
            </div>
          </div>

          <h2 className="mt-8 text-xl font-medium tracking-tight text-ink/80 sm:text-2xl">
            Enterprise Agentic Customer Support Platform
          </h2>

          <div className="mt-12">
            <Link
              to="/login"
              className="btn-primary inline-flex items-center gap-3 px-8 py-3 text-base"
            >
              Sign In
              <ArrowRight className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </main>

      <footer className="px-6 py-6 text-center text-xs text-ink/40">
        VSR AI · Enterprise Agentic Customer Support
      </footer>
    </div>
  );
}
