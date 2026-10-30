# VSR AI — Setup

You can run VSR AI three ways. Option B was used to verify the project during development.

## Option A — Docker Compose (recommended)

Requires Docker with Compose v2.

```bash
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD and JWT_SECRET
docker compose up --build
```

Then open http://localhost:8080. The backend container waits for PostgreSQL, creates tables, seeds the synthetic data if the database is empty, builds the Chroma index if it is empty, and starts uvicorn. A named volume persists the Chroma index and LangGraph checkpoints, so paused refund approvals survive restarts.

> **Verification status:** Docker was not available in the build environment, so the images and `docker compose up` have **not** been run. Verified pieces:
> - The startup logic (`python -m app.bootstrap`), run twice against an empty PostgreSQL 16 database, seeded once and then correctly skipped.
> - The frontend's `nginx.conf`, served with real nginx, passed `nginx -t`, handled SPA routing, cache headers and the `/api` proxy, and passed the full browser test suite.
> - Both YAML files parse.
>
> The CI workflow includes a job that builds both images on GitHub's runners.

## Option B — Run locally without Docker

**Prerequisites:** Python 3.11+ (developed on 3.12), Node 20+ (developed on 22), and optionally PostgreSQL 16.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# optional: point at PostgreSQL (default is SQLite in backend/data/)
export DATABASE_URL=postgresql+psycopg://vsr:change-me@localhost:5432/vsr_ai
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))")

python -m app.seed          # drop + recreate + seed synthetic data (repeatable)
python -m app.rag.ingest    # build the Chroma policy index
uvicorn app.main:app --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev                  # http://localhost:5173, proxies /api to :8000
# or a production build:
npm run build && npm run preview   # http://localhost:4173
```

### Demo accounts (synthetic)

| Account | Email | Password |
|---|---|---|
| Customer | pardha.saradhi@example.com | demo1234 |
| Customer | pavan.y@example.com | demo1234 |
| Admin | gopireddy.vsr@example.com | admin1234 |

The sign-in page offers one-click buttons for these accounts.

## Enabling LLM mode

```bash
export LLM_PROVIDER=openai OPENAI_API_KEY=sk-...        # or
export LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=...
```

`GET /api/health` reports `agent_mode`. LLM mode has not been tested (see EVALUATION.md).

## Tests

```bash
cd backend
python -m pytest -q                                               # SQLite
TEST_DATABASE_URL=postgresql+psycopg://vsr:pw@localhost:5432/vsr_test python -m pytest -q   # PostgreSQL (disposable DB!)
```

`TEST_DATABASE_URL` is reseeded during the run, so never point it at real data. Last local results: **62 passed** on SQLite and on PostgreSQL 16.

### Browser end-to-end test and screenshots

With the app running on a freshly seeded database:

```bash
pip install playwright && playwright install chromium
BASE_URL=http://localhost:4173 python scripts/browser_e2e.py
```

This drives headless Chromium through every page as a customer and an admin, completes a refund approval, asserts on visible content, fails on any console error or unexpected API error, and writes screenshots to `docs/screenshots/`.

## Configuration reference

See `.env.example`. Key variables:

- `DATABASE_URL`, `JWT_SECRET`, `LLM_PROVIDER`, `EMBEDDING_PROVIDER`
- `RATE_LIMIT_PER_MINUTE`, `CHAT_RATE_LIMIT_PER_MINUTE`, `LOGIN_RATE_LIMIT_PER_MINUTE`
- `TRUST_PROXY_HEADERS`, `REQUEST_TIMEOUT_SECONDS`, `CORS_ORIGINS`
- `CHROMA_PATH`, `CHECKPOINT_DB_PATH`

## Deployment approach

The live demo runs on Render (static frontend + FastAPI web service); see the README's Deployment section. Other practical paths:

**Single VM (simplest).** Run `docker compose up -d` on a small VM, for example 2 vCPU and 4 GB RAM. Put a TLS-terminating proxy such as Caddy in front of port 8080, set strong `POSTGRES_PASSWORD` and `JWT_SECRET`, and keep `TRUST_PROXY_HEADERS=true`, since nginx overwrites `X-Forwarded-For`.

**Managed services.**
- **Frontend:** build the static frontend with `VITE_API_BASE_URL=https://api.example.com` and host it on Netlify, Vercel or Cloudflare Pages. Add an SPA fallback to `index.html`.
- **Backend:** deploy the backend image to Render, Railway or Fly.io with a persistent disk mounted at `/app/data`, which holds Chroma and the checkpoints.
- **Database:** use managed PostgreSQL (Neon, Supabase or RDS) via `DATABASE_URL`.
- **Configuration:** set `CORS_ORIGINS` to the frontend origin.

**Constraints to respect:**
- The backend is single-process by design. Rate limits are in memory, and the SQLite checkpointer is a local file. Run one instance, or replace both before scaling out (see Known limitations in README).
- Approvals that are paused live in the checkpoint volume, so it must persist across deploys.
