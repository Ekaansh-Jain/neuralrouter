# NeuralRouter

An intelligent **LLM routing gateway**: it classifies the complexity of each
incoming query, routes it to the most appropriate free LLM, falls back
automatically when a model fails or rate-limits, and exposes a live React
dashboard of latency, cost, model usage, fallbacks, and circuit-breaker state.

> Think of it as a smart receptionist for AI requests — it sizes up the
> question, sends it to the right model, reroutes when one is down, and learns
> from a supervisor's review over time.

---

## Why this project is interesting

It is built around a few hard problems done *correctly* rather than many
features done shallowly. The notable engineering decisions:

| Decision | Why |
|---|---|
| **Heuristic classifier off the critical path** | An LLM classifier would add a network call *before* routing — tripling latency and rate-limit usage. Complexity is a cheap text-classification task. |
| **Global request deadline across the fallback chain** | Prevents *latency stacking* — three 25 s timeouts can never become a 75 s wait. |
| **Async circuit breaker with a single-probe HALF_OPEN gate** | The classic async bug is many coroutines rushing the recovery probe at once. A lock admits exactly one. |
| **Error taxonomy drives resilience** | A `429` (rate limit), a `503` (transient), and a content refusal are handled differently: cool the provider, retry, or stop. |
| **Fallback recorded separately from the routing decision** | A weak answer produced *because the primary was down* must not poison the classifier's training data. |
| **Bounded background queue** | FastAPI's default background tasks are unbounded → OOM under load. We use a bounded queue that drops work instead of crashing. |
| **Sampled evaluator** | The LLM-as-judge runs on ~10% of traffic, never inline. |
| **CPU-servable classifier upgrade (not QLoRA in the live path)** | There is no free way to serve custom 8B weights; a TF-IDF/LogReg model retrains in seconds and runs on the same box. QLoRA is documented future work. |

---

## Architecture

```
Request
  → Middleware        (request-id, CORS, rate limit)
  → Route             (/v1/chat, Pydantic validation)
  → Orchestrator      (coordinates; owns no business logic)
      → Cache check        (identical query within TTL → instant)
      → Classifier         (SIMPLE / MODERATE / COMPLEX + confidence)
      → Selector           (complexity → ordered model chain, from registry)
      → Fallback executor  (walks chain under a global deadline)
          → Circuit breaker (per model + provider cooldown)
          → Retry           (transient errors only)
          → Provider        (Groq / OpenRouter / mock)
      → Tokens + modeled cost
  → Response returned
  → Background (bounded): DB log (always) + evaluator (sampled)
```

### Layout

```
neuralrouter/
├── backend/
│   ├── app/
│   │   ├── config/        # settings + data-driven model registry & fallback chains
│   │   ├── core/          # lifespan, logging (JSON + request-id), context, deps
│   │   ├── api/
│   │   │   ├── routes/     # chat, metrics, health
│   │   │   └── schemas/    # request/response contracts (separate from DB rows)
│   │   ├── middleware/     # request-id, rate limit (slowapi)
│   │   ├── pipeline/       # orchestrator
│   │   ├── agents/
│   │   │   ├── classifier/ # base (protocol) + heuristic (v1)
│   │   │   └── evaluator/  # sampled routing judge
│   │   ├── routing/        # selector + fallback executor
│   │   ├── providers/      # base, errors (taxonomy), mock, openai_compat, groq, openrouter, hub
│   │   ├── resilience/     # circuit_breaker, retry, deadline
│   │   ├── observability/  # tokens (+ modeled cost), metrics
│   │   ├── cache/          # TTL cache
│   │   ├── background/     # bounded task runner
│   │   └── db/             # repository (in-memory or Supabase) + row schemas
│   ├── fine_tune/         # dataset export + CPU classifier training
│   └── tests/             # pytest suite for the core logic
├── frontend/             # React + Vite + Recharts dashboard
└── notebooks/            # QLoRA experiment (future work)
```

---

## Quick start

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # defaults to PROVIDER_MODE=mock (no keys needed)
uvicorn app.main:app --reload   # http://localhost:8000  (docs at /docs)
```

**Mock mode** (default) simulates provider latency and occasional failures, so
the fallback path and circuit breakers actually trigger — the dashboard fills
with realistic data without any API keys.

**Live mode**: set `PROVIDER_MODE=live` and add `GROQ_API_KEY` /
`OPENROUTER_API_KEY` in `.env`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env             # VITE_API_URL=http://localhost:8000
npm run dev                      # http://localhost:5173
```

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat` | `{ "query": "..." }` → classified, routed answer + full routing trace |
| `GET` | `/metrics/summary` | aggregates: latency percentiles, usage, fallback rate, cost, breakers |
| `GET` | `/metrics/recent` | recent request samples |
| `GET` | `/metrics/models` | model pool + fallback chains |
| `GET` | `/health`, `/ready` | liveness / readiness |

---

## Testing

The hard, framework-independent logic (circuit breaker, fallback + deadline,
classifier, cache, metrics, dataset export) is pure Python and fully covered:

```bash
cd backend
pytest          # 21 tests
ruff check app  # lint
```

---

## Known limitations (deliberate, for a solo free-tier project)

- **Single-worker assumption.** Cache, circuit breakers, and rate limits are
  per-process. Correct with one worker; would move to Redis to scale out.
- **Single-turn only.** No conversation history.
- **Modeled cost.** Free-tier spend is $0; the dashboard shows what traffic
  *would* cost at provider list prices.
- **Heuristic evaluator by default.** A real LLM-as-judge implements the same
  interface and slots in unchanged.

## Roadmap

- Swap the heuristic classifier for the trained TF-IDF model (`fine_tune/`).
- QLoRA distillation of a generative router (`notebooks/`).
- Redis-backed shared state for multi-worker deployments.
