export type User = { id: number; email: string; full_name: string; role: "customer" | "admin" };
export type ToolCall = { tool: string; success: boolean; latency_ms: number };
export type Citation = { n: number; doc_title: string; section: string; chunk_id: string; score: number; excerpt: string };
export type MessageMeta = {
  intents?: string[]; agent_path?: string[]; tools?: ToolCall[]; citations?: Citation[]; latency_ms?: number;
  active_order_id?: string | null; order_from_memory?: boolean; mode?: string; ok?: boolean; event?: string;
  pending_refund?: { refund_id: string; order_id: string; amount: number; status: string } | null;
};
export type ChatMessage = { id: number; role: "user" | "assistant"; content: string; meta: MessageMeta; created_at: string | null };
export type ConversationSummary = { id: string; title: string; updated_at: string; message_count: number };

const TOKEN_KEY = "vsr_ai_token";
const USER_KEY = "vsr_ai_user";
const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export const session = {
  get token() { return localStorage.getItem(TOKEN_KEY); },
  get user(): User | null { const u = localStorage.getItem(USER_KEY); return u ? JSON.parse(u) : null; },
  save(token: string, user: User) { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, JSON.stringify(user)); },
  clear() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); },
};

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45000);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init, signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(session.token ? { Authorization: `Bearer ${session.token}` } : {}), ...init.headers },
    });
    if (res.status === 401 && session.token) { session.clear(); window.location.assign("/login"); }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail ?? `Request failed with status ${res.status}.`);
    }
    return res.status === 204 ? (undefined as T) : res.json();
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if ((e as Error).name === "AbortError") throw new ApiError(0, "The server took too long to respond. Try again.");
    throw new ApiError(0, "Can't reach the VSR AI server. Check that the backend is running.");
  } finally { clearTimeout(timer); }
}

export const money = (v: number) => v.toLocaleString("en-US", { style: "currency", currency: "USD" });
export const time = (iso: string | null) => iso ? new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";
export const day = (iso: string | null) => iso ? new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" }) : "";
