"""Reproducible evaluation for VSR AI.

Usage (from backend/):
    python -m eval.run_eval                      # isolated temp SQLite + Chroma
    python -m eval.run_eval --database-url postgresql+psycopg://...   # use a (disposable!) Postgres DB

The run reseeds the database, so never point it at data you want to keep.
Outputs: eval/results/latest.json plus per-item CSVs in eval/results/.
"""
import argparse
import csv
import json
import os
import platform
import re
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "datasets"
OUT = HERE / "results"


def _setup_env(database_url: str | None):
    tmp = tempfile.mkdtemp(prefix="vsr_ai_eval_")
    os.environ["DATABASE_URL"] = database_url or f"sqlite:///{tmp}/eval.db"
    os.environ["CHROMA_PATH"] = f"{tmp}/chroma"
    os.environ["CHECKPOINT_DB_PATH"] = f"{tmp}/checkpoints.sqlite"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"
    os.environ["CHAT_RATE_LIMIT_PER_MINUTE"] = "100000"
    os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "100000"
    os.environ.setdefault("JWT_SECRET", "eval-secret-0123456789-not-for-production")


def jl(name):
    return [json.loads(line) for line in (DATA / name).read_text().splitlines() if line.strip()]


def write_csv(name, rows):
    if not rows:
        return
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=None)
    ap.add_argument("--mode", choices=["deterministic", "llm"], default="deterministic",
                    help="deterministic = LLM_PROVIDER=none; llm = use LLM_PROVIDER/API key from the environment")
    args = ap.parse_args()
    _setup_env(args.database_url)
    if args.mode == "deterministic":
        os.environ["LLM_PROVIDER"] = "none"
    sys.path.insert(0, str(HERE.parent))

    from fastapi.testclient import TestClient

    from app.agents.llm import llm_mode
    from app.config import get_settings
    from app.main import app
    from app.rag.embeddings import get_embedder, tokenize
    from app.rag.ingest import ingest
    from app.rag.retriever import retrieve
    from app.seed import seed

    if args.mode == "llm" and llm_mode() == "deterministic":
        sys.exit("LLM mode requested but no working LLM provider is configured (set LLM_PROVIDER and an API key). "
                 "Refusing to label deterministic results as LLM results.")
    from app.rag.grounding import expand

    seed()
    ing = ingest()
    client = TestClient(app)
    OUT.mkdir(exist_ok=True)

    def login(email, pw):
        return {"Authorization": "Bearer " + client.post("/api/auth/login", json={"email": email, "password": pw}).json()["access_token"]}

    CUST = login("pardha.saradhi@example.com", "demo1234")
    ADMIN = login("gopireddy.vsr@example.com", "admin1234")
    latencies, wall = [], []

    def ask(text, conv=None):
        t0 = time.perf_counter()
        r = client.post("/api/chat", json={"message": text, "conversation_id": conv}, headers=CUST)
        wall.append((time.perf_counter() - t0) * 1000)
        r.raise_for_status()
        j = r.json()
        latencies.append(j["message"]["meta"]["latency_ms"])
        return j

    def with_memory(text, memory):
        conv = ask("Where is my order ORD-1002?")["conversation_id"] if memory else None
        return ask(text, conv)

    # ---------------------------------------------------------- A. routing
    rows = []
    for item in jl("routing.jsonl"):
        meta = with_memory(item["text"], item["memory"])["message"]["meta"]
        got = (meta["intents"] or ["none"])[0]
        rows.append({"id": item["id"], "text": item["text"], "memory": item["memory"], "expected": item["expected"],
                     "predicted": got, "correct": got == item["expected"]})
    write_csv("routing_details.csv", rows)
    per_intent = {}
    for r in rows:
        d = per_intent.setdefault(r["expected"], {"n": 0, "correct": 0})
        d["n"] += 1
        d["correct"] += r["correct"]
    routing = {"metric": "Intent routing accuracy", "value": round(sum(r["correct"] for r in rows) / len(rows), 4),
               "n": len(rows), "method": "Supervisor's top intent (full LangGraph run via API) compared with the labelled intent. "
               "Items marked memory=true first establish ORD-1002 in the same conversation.",
               "per_intent": {k: round(v["correct"] / v["n"], 3) for k, v in per_intent.items()},
               "failures": [r for r in rows if not r["correct"]]}

    held = []
    for item in jl("routing_heldout.jsonl"):
        meta = with_memory(item["text"], item["memory"])["message"]["meta"]
        got = (meta["intents"] or ["none"])[0]
        held.append({"id": item["id"], "text": item["text"], "memory": item["memory"], "expected": item["expected"],
                     "predicted": got, "correct": got == item["expected"]})
    write_csv("routing_heldout_details.csv", held)
    routing["heldout"] = {"value": round(sum(r["correct"] for r in held) / len(held), 4), "n": len(held),
                          "note": "Written after the baseline run and before rule fixes; never used for tuning.",
                          "failures": [r for r in held if not r["correct"]]}

    # ---------------------------------------------------------- B. tool selection
    seed()
    rows, tp, fp, fn = [], 0, 0, 0
    for item in jl("tools.jsonl"):
        meta = with_memory(item["text"], item["memory"])["message"]["meta"]
        called = sorted({t["tool"] for t in meta["tools"]})
        exp = sorted(set(item["expected_tools"]))
        tp += len(set(called) & set(exp)); fp += len(set(called) - set(exp)); fn += len(set(exp) - set(called))
        rows.append({"id": item["id"], "text": item["text"], "expected": "|".join(exp), "called": "|".join(called),
                     "exact_match": called == exp})
    write_csv("tool_selection_details.csv", rows)
    tools = {"metric": "Tool-selection accuracy (exact set match)", "value": round(sum(r["exact_match"] for r in rows) / len(rows), 4),
             "n": len(rows), "tool_call_precision": round(tp / (tp + fp), 4) if tp + fp else None,
             "tool_call_recall": round(tp / (tp + fn), 4) if tp + fn else None,
             "method": "The set of tools actually executed during the turn (from the execution trace) must equal the labelled set.",
             "failures": [r for r in rows if not r["exact_match"]]}

    # ---------------------------------------------------------- C. task completion
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Order, RefundRequest, ReturnRequest

    tasks = json.loads((DATA / "tasks.json").read_text())
    rows = []
    for task in tasks:
        seed()
        conv, replies, ok, why = None, [], True, []
        for t in task["turns"]:
            j = ask(t, conv)
            conv = j["conversation_id"]
            replies.append(j["message"])
        if task.get("approve"):
            pend = client.get("/api/admin/refunds?status=pending", headers=ADMIN).json()
            if pend:
                client.post(f"/api/admin/refunds/{pend[0]['refund_id']}/decision",
                            json={"decision": task["approve"], "note": "Evaluation decision"}, headers=ADMIN)
        final = client.get(f"/api/chat/conversations/{conv}", headers=CUST).json()["messages"][-1]["content"]
        db = SessionLocal()
        for c in task["checks"]:
            if "turn" in c:
                msg = replies[c["turn"]]
                for s in c.get("contains", []):
                    if s.lower() not in msg["content"].lower():
                        ok = False; why.append(f"turn {c['turn']} missing '{s}'")
                for s in c.get("not_contains", []):
                    if s.lower() in msg["content"].lower():
                        ok = False; why.append(f"turn {c['turn']} unexpectedly contains '{s}'")
                if c.get("has_citations") and not msg["meta"]["citations"]:
                    ok = False; why.append("no citations")
                for k, v in c.get("meta", {}).items():
                    if msg["meta"].get(k) != v:
                        ok = False; why.append(f"meta {k}={msg['meta'].get(k)}")
            elif c.get("db"):
                order = db.scalar(select(Order).where(Order.order_number == c["order"]))
                if c["db"] == "return_exists":
                    if not db.scalar(select(ReturnRequest).where(ReturnRequest.order_id == order.id)):
                        ok = False; why.append("no return row")
                elif c["db"] == "refund_status":
                    st = [r.status for r in db.scalars(select(RefundRequest).where(RefundRequest.order_id == order.id))]
                    if c["status"] not in st:
                        ok = False; why.append(f"refund statuses {st}")
                elif c["db"] == "refund_count":
                    n = len(db.scalars(select(RefundRequest).where(RefundRequest.order_id == order.id)).all())
                    if n != c["count"]:
                        ok = False; why.append(f"refund count {n}")
            elif c.get("final_message_contains") and c["final_message_contains"].lower() not in final.lower():
                ok = False; why.append("final notification missing")
        db.close()
        rows.append({"id": task["id"], "name": task["name"], "turns": len(task["turns"]), "completed": ok, "notes": "; ".join(why)})
    write_csv("task_completion_details.csv", rows)
    completion = {"metric": "Task completion rate", "value": round(sum(r["completed"] for r in rows) / len(rows), 4),
                  "n": len(rows), "method": "Scripted multi-turn scenarios (including admin approve/reject) checked against "
                  "response content, citations, memory flags and resulting database rows.",
                  "failures": [r for r in rows if not r["completed"]]}

    # ---------------------------------------------------------- D. retrieval precision@5
    rows = []
    for item in jl("retrieval.jsonl"):
        got = [r.id.rsplit("::", 1)[0] for r in retrieve(expand(item["query"]), k=5)]
        rel = set(item["relevant"])
        hits = [g in rel for g in got]
        first = next((i + 1 for i, h in enumerate(hits) if h), None)
        rows.append({"id": item["id"], "query": item["query"], "relevant": "|".join(sorted(rel)), "top5": "|".join(got),
                     "precision_at_5": sum(hits) / 5, "max_possible_p5": min(5, len(rel)) / 5,
                     "recall_at_5": len(rel & set(got)) / len(rel), "hit_at_1": bool(hits and hits[0]),
                     "reciprocal_rank": 1 / first if first else 0.0})
    write_csv("retrieval_details.csv", rows)
    mean = lambda k: round(statistics.mean(r[k] for r in rows), 4)  # noqa: E731
    retrieval = {"metric": "Retrieval Precision@5", "value": mean("precision_at_5"), "n": len(rows),
                 "ceiling": mean("max_possible_p5"), "recall_at_5": mean("recall_at_5"), "hit_at_1": mean("hit_at_1"),
                 "mrr": mean("reciprocal_rank"),
                 "method": "Fraction of the top-5 retrieved chunks whose policy section is labelled relevant. Each query "
                 "has only 1-2 relevant sections, so the attainable ceiling is reported alongside the score. Queries pass through the "
                 "same synonym expansion the knowledge agent uses (added in v3)."}

    # ---------------------------------------------------------- E. groundedness + abstention
    def support(sentence, chunks):
        toks = set(tokenize(sentence))
        if not toks:
            return True
        return max(len(toks & set(tokenize(c))) / len(toks) for c in chunks) >= 0.8 if chunks else False

    # Any response that declines to state unsupported facts counts as abstaining.
    ABSTAIN_MARKERS = ("couldn't find that", "couldn't find products matching")
    rows, abst = [], []
    for item in jl("retrieval.jsonl"):
        j = ask(item["query"])
        content, meta = j["message"]["content"], j["message"]["meta"]
        cites = meta["citations"]
        abstained = "couldn't find that" in content
        kb_answered = "knowledge_agent" in meta["agent_path"] and bool(cites)
        chunk_texts = [r.text for r in retrieve(expand(item["query"]), k=5) if r.id in {c["chunk_id"] for c in cites}]
        kb_text = content.split("**From our policies:**", 1)[1] if "**From our policies:**" in content else content
        body = re.sub(r"\[\d+\]", "", kb_text)
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if len(s.split()) >= 4]
        sup = [support(s, chunk_texts) for s in sents] if kb_answered else []
        rel_cited = bool({c["chunk_id"].rsplit("::", 1)[0] for c in cites} & set(item["relevant"]))
        rows.append({"id": item["id"], "query": item["query"], "routed_to": "|".join(meta["agent_path"]),
                     "kb_answered": kb_answered, "abstained": abstained, "sentences": len(sents) if kb_answered else 0,
                     "supported_sentences": sum(sup), "cites_relevant_section": rel_cited})
    splits = {"unanswerable.jsonl": "dev", "unanswerable_heldout.jsonl": "seen_heldout_v1", "unanswerable_heldout_v2.jsonl": "heldout_v2"}
    for fname, split in splits.items():
        for item in jl(fname):
            content = ask(item["query"])["message"]["content"]
            abst.append({"id": item["id"], "split": split, "query": item["query"],
                         "abstained": any(x in content for x in ABSTAIN_MARKERS)})
    # fresh answerable held-out questions (v2): does the agent answer, with a relevant citation?
    ans_v2 = []
    for item in jl("answerable_heldout_v2.jsonl"):
        j = ask(item["query"])
        meta, content = j["message"]["meta"], j["message"]["content"]
        cited = {c["chunk_id"].rsplit("::", 1)[0] for c in meta["citations"]}
        ans_v2.append({"id": item["id"], "query": item["query"], "routed_to": "|".join(meta["agent_path"]),
                       "answered": "knowledge_agent" in meta["agent_path"] and bool(meta["citations"]),
                       "cites_relevant_section": bool(cited & set(item["relevant"]))})
    write_csv("answerable_heldout_v2_details.csv", ans_v2)
    write_csv("groundedness_details.csv", rows)
    write_csv("abstention_details.csv", abst)
    answered = [r for r in rows if r["kb_answered"]]
    dev_abs = [a for a in abst if a["split"] == "dev"]
    held_abs = [a for a in abst if a["split"] == "seen_heldout_v1"]
    v2_abs = [a for a in abst if a["split"] == "heldout_v2"]
    total_s = sum(r["sentences"] for r in answered)
    grounded = {"metric": "Answer groundedness (lexical support)",
                "value": round(sum(r["supported_sentences"] for r in answered) / total_s, 4) if total_s else None,
                "n": len(rows), "n_kb_answers": len(answered), "answered_rate": round(len(answered) / len(rows), 4),
                "relevant_citation_rate": round(sum(r["cites_relevant_section"] for r in answered) / len(answered), 4) if answered else None,
                "abstention_definition": "Response contains no policy/product claim: the knowledge agent's 'couldn't find that' or the product agent's 'couldn't find products matching'.",
                "abstention_accuracy_unanswerable": round(sum(a["abstained"] for a in dev_abs) / len(dev_abs), 4), "n_unanswerable": len(dev_abs),
                "abstention_accuracy_heldout": round(sum(a["abstained"] for a in held_abs) / len(held_abs), 4), "n_unanswerable_heldout": len(held_abs),
                "abstention_heldout_note": "The v1 held-out unanswerable set was inspected while designing the v3 gate, so it is now reported as 'seen'.",
                "heldout_v2": {
                    "abstention_accuracy": round(sum(a["abstained"] for a in v2_abs) / len(v2_abs), 4), "n_unanswerable": len(v2_abs),
                    "answered_rate": round(sum(a["answered"] for a in ans_v2) / len(ans_v2), 4),
                    "relevant_citation_rate": round(sum(a["cites_relevant_section"] for a in ans_v2) / len(ans_v2), 4),
                    "n_answerable": len(ans_v2),
                    "note": "Written before the v3 answerability gate was implemented; never used for tuning."},
                "method": "Scored only on turns answered by the knowledge agent with citations (answered_rate shows how many "
                "policy questions reached it; the rest were routed elsewhere). An answer sentence is 'supported' when >=80% of its content tokens appear in one cited chunk. "
                "In deterministic mode answers are extractive, so high support is expected by construction; the more "
                "informative numbers are relevant_citation_rate and abstention accuracy on unanswerable questions.",
                "llm_judge": "Not Evaluated: LLM-as-judge groundedness requires an LLM API key, which was not configured for this run."}

    # ---------------------------------------------------------- F. latency
    def pct(xs, p):
        xs = sorted(xs)
        return round(xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))], 1)

    latency = {"metric": "API response latency", "n": len(wall),
               "graph_ms": {"mean": round(statistics.mean(latencies), 1), "p50": pct(latencies, 0.5), "p95": pct(latencies, 0.95), "max": round(max(latencies), 1)},
               "api_ms": {"mean": round(statistics.mean(wall), 1), "p50": pct(wall, 0.5), "p95": pct(wall, 0.95), "max": round(max(wall), 1)},
               "method": "Every POST /api/chat issued during this evaluation, measured in-process (FastAPI TestClient, no network hop). "
               "graph_ms = LangGraph execution; api_ms = full request including auth and persistence.",
               "value": pct(wall, 0.5)}

    s = get_settings()
    result = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "version": "v3",
        "results_mode": args.mode,
        "baseline_file": "eval/results/baseline_v1.json",
        "conditions": {"agent_mode": llm_mode(), "llm_provider": s.llm_provider, "embedder": get_embedder().name,
                       "database": s.database_url.split(":")[0], "vector_store": "chroma", "chunks_indexed": ing["chunks"],
                       "python": platform.python_version(), "platform": platform.platform(), "cpu_count": os.cpu_count(),
                       "note": "All numbers come from deterministic agents (no LLM). Datasets were written by the project author. Routing rules were "
                       "revised once after v1 and the abstention gate was redesigned in v3 using dev sets, so dev scores are optimistic. "
                       "routing_heldout and the *_heldout_v2 sets were never used for tuning."},
        "metrics": {"routing": routing, "tool_selection": tools, "task_completion": completion,
                    "retrieval": retrieval, "groundedness": grounded, "latency": latency},
    }
    name = "latest.json" if args.mode == "deterministic" else "latest_llm.json"
    (OUT / name).write_text(json.dumps(result, indent=2))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("value", "n", "ceiling", "mrr", "abstention_accuracy_unanswerable", "abstention_accuracy_heldout", "answered_rate", "relevant_citation_rate", "graph_ms", "api_ms", "heldout")}
                      for k, v in result["metrics"].items()}, indent=1))


if __name__ == "__main__":
    main()
