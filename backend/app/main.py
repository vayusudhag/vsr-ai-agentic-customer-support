"""VSR AI - FastAPI application entry point."""
import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.llm import llm_mode
from app.config import get_settings
from app.db import init_db
from app.observability import configure_logging
from app.routers import admin, auth, chat, evaluation, store

log = configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    log.info("VSR AI started (env=%s, agent mode=%s)", settings.environment, llm_mode())
    yield


app = FastAPI(title="VSR AI API", version="1.0.0", lifespan=lifespan,
              description="VSR AI - Enterprise Agentic Customer Support Platform")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

_hits: dict[str, deque] = defaultdict(deque)


def _client_id(request: Request) -> str:
    if settings.trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _bucket(request: Request) -> tuple[str, int]:
    path, method = request.url.path, request.method
    if method == "POST" and path == "/api/auth/login":
        return "login", settings.login_rate_limit_per_minute
    if method == "POST" and path == "/api/chat":
        return "chat", settings.chat_rate_limit_per_minute
    return "api", settings.rate_limit_per_minute


@app.middleware("http")
async def reliability(request: Request, call_next):
    # In-memory sliding-window rate limits per client and bucket (single-process scope).
    if request.url.path.startswith("/api/") and request.method != "OPTIONS":
        name, limit = _bucket(request)
        key = f"{name}:{_client_id(request)}"
        now, window = time.monotonic(), _hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            return JSONResponse({"detail": "Too many requests. Wait a minute and try again."}, status_code=429,
                                headers={"Retry-After": "60"})
        window.append(now)
    t0 = time.perf_counter()
    try:
        response = await asyncio.wait_for(call_next(request), timeout=settings.request_timeout_seconds)
    except asyncio.TimeoutError:
        return JSONResponse({"detail": "The request took too long. Try again."}, status_code=504)
    response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - t0) * 1000:.1f}"
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    msgs = [f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()]
    return JSONResponse({"detail": "; ".join(msgs) or "Invalid request."}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("unhandled error: %s", exc)
    return JSONResponse({"detail": "Internal error. The incident was logged."}, status_code=500)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "VSR AI", "agent_mode": llm_mode()}


for r in (auth.router, chat.router, store.router, admin.router, evaluation.router):
    app.include_router(r)
