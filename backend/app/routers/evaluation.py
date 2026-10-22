import json
from pathlib import Path

from fastapi import APIRouter, Depends

from app.config import BASE_DIR
from app.models import User
from app.security import get_current_user

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])
RESULTS_DIR = BASE_DIR / "eval" / "results"
HISTORY = [("v1", "baseline_v1.json", "First run, before any tuning"),
           ("v2", "v2_deterministic/latest.json", "Router rules revised; sentence-overlap abstention"),
           ("v3", "latest.json", "IDF-coverage answerability gate + synonym expansion")]


def _load(rel: str) -> dict | None:
    p = Path(RESULTS_DIR / rel)
    return json.loads(p.read_text()) if p.exists() else None


def _summary(m: dict) -> dict:
    g = m["groundedness"]
    return {"routing_dev": m["routing"]["value"], "routing_heldout": m["routing"].get("heldout", {}).get("value"),
            "tool_selection": m["tool_selection"]["value"], "task_completion": m["task_completion"]["value"],
            "precision_at_5": m["retrieval"]["value"], "answered_rate": g.get("answered_rate"),
            "abstention_dev": g.get("abstention_accuracy_unanswerable"),
            "abstention_heldout_v1": g.get("abstention_accuracy_heldout"),
            "abstention_heldout_v2": (g.get("heldout_v2") or {}).get("abstention_accuracy"),
            "answered_heldout_v2": (g.get("heldout_v2") or {}).get("answered_rate"),
            "latency_p50_ms": m["latency"]["api_ms"]["p50"]}


@router.get("/results")
def results(_: User = Depends(get_current_user)):
    latest = _load("latest.json")
    if latest is None:
        return {"available": False, "message": "No evaluation run found. Run: python -m eval.run_eval"}
    history = []
    for version, rel, desc in HISTORY:
        d = _load(rel)
        if d:
            history.append({"version": version, "description": desc, "run_at": d["run_at"], **_summary(d["metrics"])})
    llm = _load("latest_llm.json")
    return {"available": True, **latest, "baseline": _load("baseline_v1.json"), "history": history,
            "llm": llm, "llm_status": "evaluated" if llm else
            "Not Evaluated: no LLM API key was configured for any evaluation run. Run `python -m eval.run_eval --mode llm` "
            "with LLM_PROVIDER and an API key set to produce latest_llm.json."}
