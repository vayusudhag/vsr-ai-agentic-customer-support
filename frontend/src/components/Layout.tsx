import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { BarChart3, FlaskConical, LogOut, Menu, MessageSquare, Package, RotateCcw, ShoppingBag, X } from "lucide-react";
import { Logo } from "./Logo";
import { useAuth } from "../lib/auth";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const items = user?.role === "admin"
    ? [{ to: "/admin", label: "VSR AI Dashboard", icon: BarChart3 }, { to: "/evaluation", label: "AI evaluation", icon: FlaskConical },
       { to: "/app/products", label: "Product catalog", icon: ShoppingBag }]
    : [{ to: "/app/chat", label: "Support chat", icon: MessageSquare }, { to: "/app/orders", label: "My orders", icon: Package },
       { to: "/app/returns", label: "Returns & refunds", icon: RotateCcw }, { to: "/app/products", label: "Product catalog", icon: ShoppingBag },
       { to: "/evaluation", label: "AI evaluation", icon: FlaskConical }];

  const sidebar = (
    <div className="flex h-full flex-col bg-ink px-3 pb-4 pt-5 text-white">
      <div className="flex items-center justify-between px-2"><Logo light />
        <button className="text-white/60 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu"><X className="h-5 w-5" /></button></div>
      <nav className="mt-8 space-y-0.5" aria-label="Main">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} onClick={() => setOpen(false)}
            className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-[14px] transition-colors ${isActive ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"}`}>
            <Icon className="h-4 w-4" aria-hidden />{label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto rounded-lg bg-ink-2 p-3">
        <div className="flex items-center gap-3">
          <div className="grid h-8 w-8 place-items-center rounded-full bg-ink-3 font-display text-xs font-semibold">
            {user?.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">{user?.full_name}</div>
            <div className="text-xs capitalize text-white/50">{user?.role}</div>
          </div>
          <button onClick={() => { logout(); nav("/login"); }} className="rounded-md p-1.5 text-white/50 hover:bg-white/10 hover:text-white" aria-label="Sign out" title="Sign out">
            <LogOut className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-[100dvh] overflow-hidden">
      <aside className="hidden w-60 shrink-0 lg:block">{sidebar}</aside>
      {open && <div className="fixed inset-0 z-40 lg:hidden"><div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
        <div className="absolute inset-y-0 left-0 w-64">{sidebar}</div></div>}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-line bg-white px-4 py-3 lg:hidden">
          <button onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button><Logo />
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
