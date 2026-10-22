# VSR AI — Evaluation

All results below were produced by `backend/eval/run_eval.py` and are stored in `backend/eval/results/`. Nothing here is hand-entered. The evaluation dashboard in the app reads the same JSON files.

## Deterministic versus LLM-powered results

VSR AI has two agent modes:

| | Deterministic (`LLM_PROVIDER=none`) | LLM-powered (`LLM_PROVIDER=openai` or `anthropic`) |
|---|---|---|
| Routing | Rule-based intent classifier | LLM structured output (`RouteDecision`), falling back to rules on error |
| Orders / Products agents | Policy-driven tool calls | LLM tool-calling loop (`bind_tools`, up to 4 steps) |
| Knowledge answers | Extractive sentences with citations | LLM synthesis restricted to retrieved policy text |
| Returns & refunds | Deterministic | Deterministic (sensitive actions never delegated to the LLM) |
| **Evaluated?** | **Yes — every number in this document** | **Not Evaluated** |

**LLM mode is implemented but has never been executed or evaluated.** No API key was available in the build environment. To evaluate it, set `LLM_PROVIDER` and a key, then run `python -m eval.run_eval --mode llm`. Results are written to a separate `latest_llm.json`. The script refuses to run in LLM mode without a working provider, so deterministic numbers can never be mislabelled as LLM results.

## Test conditions (latest run, v3)

- Agent mode: deterministic. Embeddings: `hashing-1024`. Vector store: Chroma with 33 chunks from 6 policy documents.
- Database: isolated temporary SQLite, reseeded by the script. The same suite is run against PostgreSQL 16 in CI with `--database-url`.
- Python 3.12.3, Linux, single process. Latency is measured in-process with FastAPI's TestClient, so there is no network hop.
- The script reseeds the database before each task scenario, so runs are reproducible.

## Datasets

| File | Size | Purpose |
|---|---|---|
| `routing.jsonl` | 50 | Dev set for intent routing (10 intents, including memory follow-ups) |
| `routing_heldout.jsonl` | 20 | Held-out routing set, written after v1 and never used for tuning |
| `tools.jsonl` | 20 | Expected tool sets per request |
| `tasks.json` | 14 | Multi-turn scenarios with content, metadata and database checks, including admin approve/reject |
| `retrieval.jsonl` | 30 | Answerable policy questions with relevant section labels |
| `unanswerable.jsonl` | 8 | Dev out-of-scope questions |
| `unanswerable_heldout.jsonl` | 6 | Held-out in v2; **inspected while designing v3**, so now reported as "seen" |
| `answerable_heldout_v2.jsonl` | 10 | Fresh answerable questions, written before v3 and never used for tuning |
| `unanswerable_heldout_v2.jsonl` | 10 | Fresh out-of-scope questions, written before v3 and never used for tuning |

All datasets were written by the project author, who also wrote the rules. Held-out scores are the more trustworthy numbers.

## Results — v3 (latest)

| Metric | Result | n | Method |
|---|---|---|---|
| **Intent routing accuracy (held-out)** | **95.0%** | 20 | Top supervisor intent from a full graph run, compared with the label |
| Intent routing accuracy (dev) | 100% | 50 | Optimistic: rules were revised once on this set |
| **Tool-selection accuracy** | **100%** | 20 | Exact match between executed tool set and labelled set; tool-call precision and recall are both 100% |
| **Task completion rate** | **100%** | 14 | Scripted multi-turn scenarios checked against responses, citations, memory flags and DB rows |
| **Retrieval Precision@5** | **0.233** | 30 | Relevant chunks in top 5 ÷ 5. **Ceiling on this set is 0.26**, since each query has only 1–2 relevant sections |
| Recall@5 / Hit@1 / MRR | 91.7% / 73.3% / 0.842 | 30 | Same retrieval runs |
| **Answer groundedness (lexical)** | **100%** | 26 answers | Share of answer sentences with ≥80% of content tokens in one cited chunk |
| Answers cite a relevant section | 92.3% | 26 | |
| Answer rate, answerable dev questions | 86.7% | 30 | Share answered by the knowledge agent with citations |
| **Abstention, fresh held-out (v2)** | **70.0%** | 10 | Out-of-scope questions that got a refusal instead of policy text |
| **Answered, fresh held-out (v2)** | **80.0%** | 10 | Both misses were routing errors, not gate errors |
| Abstention, dev | 100% | 8 | |
| Abstention, previously seen held-out | 100% | 6 | Not independent, since it was seen during v3 design |
| LLM-as-judge groundedness | **Not Evaluated** | – | Requires an LLM API key |
| **API latency** | **p50 28 ms · p95 42 ms** | 185 requests | Full `POST /api/chat`, in-process. Mean graph execution: 19 ms |

**Read the groundedness number carefully.** In deterministic mode, answers are extracted from retrieved text, so 100% lexical support is expected by construction. It shows the citation plumbing is correct; it says nothing about the quality of generated language. The informative grounding numbers are the relevant-citation rate and the abstention results.

## Run history

| Version | Change | Routing dev | Routing held-out | Tools | Tasks | Answer rate | Abstain (dev) | Abstain (fresh held-out v2) |
|---|---|---|---|---|---|---|---|---|
| v1 | First run, no tuning | 88.0% | – | 95.0% | 100% | 100%* | 75.0%* | – |
| v2 | Router rules generalised; abstention = sentence-overlap ≥ 0.25 | 100% | 95.0% | 100% | 100% | 93.3% | 100% | – |
| v3 | IDF-coverage answerability gate (τ = 0.20), synonym expansion, policy-scoped citations | 100% | 95.0% | 100% | 100% | 86.7% | 100% | 70.0% |

\* v1 used an earlier metric definition. Groundedness counted misrouted turns, and abstention only recognised the knowledge agent's refusal, not the product agent's "no matching products". Snapshots: `results/baseline_v1.json`, `results/v2_deterministic/`, and `results/latest.json`.

### What changed in v3, and the trade-off

In v2, the held-out abstention set exposed a weakness: only 3 of 6 out-of-scope questions were refused. The sentence-overlap rule accepted any answer sharing one word with the question. In v3 the knowledge agent instead measures how much of the question's *information* (IDF-weighted, with terms absent from all policies weighted ×2) the best chunk covers. A small synonym map ("Canada" → "internationally", "money back" → "refund") runs first.

The threshold was chosen on dev data only. In an offline sweep of the gate alone (retrieval + coverage, no routing) on those 30 answerable and 14 unanswerable questions, τ = 0.20 gave 90% answer rate and 92.9% abstention, versus v2's 93.3% and 78.6% on the same questions. On the fresh v2 held-out sets, v3 refused 7 of 10 out-of-scope questions and answered 8 of 10 answerable ones.

The cost is visible: on the dev set, the answer rate fell from 93.3% to 86.7%. Questions like "Can I return an order that hasn't arrived yet?" now fall just below the gate.

### Known failures in the latest run

- **Routing (held-out):** "Was my refund processed?" is routed to `policy_question` instead of `refund_status`, because "processed" isn't a status cue.
- **Abstention (held-out v2):** "installation for the standing desk", "rewards credit card" and "leave a product review" received loosely related policy sentences instead of a refusal. Shared terms (desk, credit, product) push coverage above the threshold.
- **Answer rate (held-out v2):** "Do I need an RMA number to return something?" and "What if the price drops after I buy something?" were routed to the product agent ("something" and "buy" are product cues), so the knowledge agent never answered.

Per-item CSVs for every metric are in `backend/eval/results/`.

## Reproducing

```bash
cd backend
pip install -r requirements.txt
python -m eval.run_eval                       # deterministic, isolated temp DB
python -m eval.run_eval --database-url postgresql+psycopg://user:pass@host/disposable_db
LLM_PROVIDER=openai OPENAI_API_KEY=... python -m eval.run_eval --mode llm   # writes latest_llm.json
```
