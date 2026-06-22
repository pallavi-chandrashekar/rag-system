# Architecture

This document describes the design of the Enterprise RAG Reference
Architecture: a modular, multi-tenant Retrieval-Augmented Generation system
built for grounded answers, auditability, and incremental hardening toward
production.

## Goals

- **Grounded answers** — every response is generated only from retrieved
  context and cites its sources; the system abstains when it cannot ground.
- **Multi-tenancy** — strict per-tenant data isolation at the database layer.
- **Observability** — latency, retrieval counts, confidence, model, and token
  usage are recorded for every query.
- **Modularity** — retrieval, generation, routing, ingestion, and evaluation
  are separate, independently testable services.

## Component Overview

```
        ┌────────────┐    X-Tenant-ID     ┌──────────────────────────┐
 User → │  React UI  │ ─────────────────▶ │       FastAPI API        │
        └────────────┘                    │      (backend/api)       │
                                          └────────────┬─────────────┘
                                                       │
                       ┌───────────────────────────────┼───────────────────────────────┐
                       ▼                               ▼                                 ▼
                ┌────────────┐              ┌────────────────────┐            ┌────────────────────┐
                │   Router   │              │ Retrieval Service  │            │   LLM Service      │
                │ (intent)   │              │ vector + keyword   │            │ grounded gen +     │
                │            │              │ fusion, tenant     │            │ unknown-answer     │
                └────────────┘              │ scoped, confidence │            │ + token usage      │
                                            └─────────┬──────────┘            └────────────────────┘
                                                      ▼
                                          ┌────────────────────────┐
                                          │ PostgreSQL + pgvector   │
                                          │ documents / chunks /    │
                                          │ chat_sessions           │
                                          └────────────────────────┘
```

## Request Lifecycle (`POST /api/v1/search`)

1. **Route** — the query is classified into one of three modes (Step 7):
   - `LLM_ONLY` — greetings / general chat, no retrieval.
   - `SUMMARY` — summarize the tenant's corpus.
   - `SEARCH` — hybrid retrieval over the tenant's chunks.
2. **Rewrite** — for follow-up questions, chat history is used to produce a
   standalone query (coreference resolution).
3. **Retrieve** — `RetrievalService` runs tenant-scoped hybrid retrieval and
   returns ranked candidates with per-signal scores.
4. **Confidence gate** — if there are no chunks or the top combined score is
   below `RAG_MIN_CONFIDENCE_SCORE`, the system returns the unknown-answer
   response and emits no citations (Step 6).
5. **Generate** — otherwise the grounded prompt (Step 5) is sent to the chat
   model, which must answer only from the supplied context and cite sources.
6. **Respond** — the API returns `answer`, `sources`, `confidence`, `mode`,
   `tenant_id`, `latency_ms`, and `token_usage`.

## Retrieval

Hybrid retrieval fuses two signals, both strictly filtered by `tenant_id`:

- **Vector** — cosine similarity over pgvector embeddings, filtered by a
  similarity floor (`RAG_VECTOR_FLOOR`).
- **Keyword** — lexical overlap between query terms and chunk text, plus
  Postgres full-text candidates so keyword-only matches surface.

The final ranking score is a weighted combination:

```
combined_score = RAG_VECTOR_WEIGHT * vector_score
               + RAG_KEYWORD_WEIGHT * keyword_score      (defaults 0.7 / 0.3)
```

`confidence` is the best combined score in the result set and drives the
unknown-answer gate.

## Data Model

| Table           | Purpose                                                  |
| --------------- | -------------------------------------------------------- |
| `documents`     | One row per uploaded file, owned by a `tenant_id`.       |
| `chunks`        | Text chunks + `Vector` embeddings, owned by `tenant_id`. |
| `chat_sessions` | Persisted conversation history per tenant.               |

Every retrieval and mutation query includes a `tenant_id` predicate; there is
no code path that reads chunks across tenants.

## Embeddings

The reference stack ships with **local** `sentence-transformers`
(`all-MiniLM-L6-v2`, 384-dim) so it is fully runnable offline with no embedding
API key. Set `EMBEDDING_PROVIDER=openai` (and a matching `Vector()` dimension)
to switch to `text-embedding-3-small`. See the roadmap for a pluggable vector
store adapter.

## Observability

Each query emits a structured log line with `tenant`, `mode`,
`retrieval_count`, `selected_source_count`, `confidence`, `model`,
`latency_ms`, and `tokens`. These map directly onto metrics/traces when wired to
OpenTelemetry (roadmap).

## Evaluation

`backend/evaluation/evaluator.py` computes offline quality metrics — citation
rate, average source count, unknown-answer accuracy, relevance, and a
groundedness proxy — against a labelled case set or the live API.
