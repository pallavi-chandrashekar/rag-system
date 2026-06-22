# Enterprise RAG Reference Architecture

A production-style, multi-tenant **Retrieval-Augmented Generation (RAG)**
reference implementation built with **FastAPI**, **React**, **PostgreSQL +
pgvector**, and a pluggable LLM/embedding layer.

It is designed to demonstrate the engineering practices that separate a demo
from a deployable system: **grounded answers with citations**, **strict
multi-tenant isolation**, **hybrid retrieval**, **abstention on low
confidence**, **observability**, and a built-in **evaluation harness**.

![status](https://img.shields.io/badge/status-reference--architecture-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## Overview

The system answers questions over a tenant's uploaded documents. An intent
router decides whether to chat directly, summarize, or run retrieval. For
retrieval queries it performs tenant-scoped **hybrid search**, generates an
answer **grounded only in the retrieved context**, returns **citations** and a
**confidence score**, and **abstains** ("I don't know based on the available
documents.") when it cannot ground an answer.

```
React UI ──X-Tenant-ID──▶ FastAPI ──▶ Router ──▶ Retrieval (vector+keyword, tenant-scoped)
                                          │            │
                                          └─▶ Grounded LLM ◀── ranked, cited context
                                                       │
                              PostgreSQL + pgvector (documents / chunks / chat_sessions)
```

See [`docs/architecture.md`](docs/architecture.md) for the full design.

---

## Features

- 🧠 **Intent router** — `LLM_ONLY`, `SUMMARY`, `SEARCH` modes.
- 🔎 **Hybrid retrieval** — weighted vector + keyword fusion, tenant-scoped.
- 📌 **Grounded answers + citations** — every answer cites the chunks it used.
- 🤷 **Abstention** — returns "I don't know..." on no/low-confidence retrieval.
- 🔐 **Multi-tenancy** — strict per-tenant isolation at the database layer.
- 📊 **Observability** — latency, retrieval counts, confidence, model, tokens.
- 🧪 **Evaluation harness** — citation rate, groundedness, unknown accuracy.
- 💬 **Persistent chat sessions** with rename/delete.
- 📂 **PDF/TXT/MD ingestion** with sentence-aware chunking.

---

## Tech Stack

| Layer        | Technology                                        |
| ------------ | ------------------------------------------------- |
| Frontend     | React + Vite                                      |
| Backend      | FastAPI (Python), SQLAlchemy                       |
| Database     | PostgreSQL + `pgvector`                            |
| Embeddings   | `sentence-transformers` (local) or OpenAI         |
| Generation   | OpenAI chat models (`gpt-4o-mini` default)         |
| Ingestion    | `pypdf`, sentence-aware chunker                    |

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- An OpenAI API key (used for generation; embeddings run locally by default)

### Configure
```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

### Run
```bash
docker-compose up -d --build
```

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

### Try it
1. Enter a Tenant ID (e.g. `demo-corp`) in the sidebar.
2. Upload a sample doc from [`data/sample_documents/`](data/sample_documents/).
3. Ask: *"What is the remote work policy?"* — see the grounded answer, its
   confidence, latency, and citations.
4. Ask something off-topic — the system abstains instead of guessing.

---

## Multi-Tenancy

Every `document`, `chunk`, and `chat_session` is owned by a `tenant_id`. All
retrieval and read queries are filtered by `tenant_id` at the SQL layer, so one
tenant can never read another tenant's data. Requests are scoped via the
`X-Tenant-ID` header. There is no cross-tenant read path in the codebase, which
the test suite asserts directly.

---

## Hybrid Retrieval

Retrieval fuses two tenant-scoped signals into a single ranking score:

```
combined_score = RAG_VECTOR_WEIGHT * vector_score      # cosine similarity
               + RAG_KEYWORD_WEIGHT * keyword_score     # lexical overlap
                                                        # defaults: 0.7 / 0.3
```

- **Vector** candidates come from pgvector cosine search above a similarity
  floor.
- **Keyword** candidates come from Postgres full-text search, so exact-term
  matches surface even when embeddings miss them.
- `confidence` = the best `combined_score`, which gates abstention.

Tunable via `RAG_VECTOR_WEIGHT`, `RAG_KEYWORD_WEIGHT`, `RAG_VECTOR_FLOOR`,
`RAG_TOP_K`, and `RAG_MIN_CONFIDENCE_SCORE`.

---

## Responsible AI

Implemented (not just documented) — see
[`docs/responsible-ai.md`](docs/responsible-ai.md):

- **Tenant isolation** enforced at the data layer.
- **Grounded generation** — answers use only retrieved context.
- **Citations** for auditability.
- **Abstention** on low confidence.
- **Minimal logging** — metadata only, never raw answers or document text.

---

## Evaluation

`backend/evaluation/evaluator.py` provides an offline harness that scores:

- **citation_rate** — answered queries that carry ≥ 1 source
- **avg_source_count** — citations per answer
- **unknown_answer_accuracy** — correct abstention on out-of-scope queries
- **avg_relevance** — expected-keyword coverage
- **avg_groundedness** — answer terms supported by cited sources

Run against a live stack:
```bash
RAG_BASE_URL=http://localhost:8000 RAG_EVAL_TENANT=demo-corp \
  python -m backend.evaluation.evaluator
```

---

## Observability

Every query emits a structured log line:

```
rag_query tenant=demo-corp mode=hybrid retrieval_count=5 selected_sources=5 \
  confidence=0.812 model=gpt-4o-mini latency_ms=734 tokens=512
```

The API response also returns `latency_ms`, `confidence`, and `token_usage` so
clients can display and audit per-answer cost and quality. These fields map
directly onto OpenTelemetry spans/metrics (roadmap).

---

## Configuration

All behaviour is environment-driven (see [`.env.example`](.env.example)):

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Generation model |
| `EMBEDDING_PROVIDER` | `local` | `local` or `openai` |
| `RAG_TOP_K` | `5` | Chunks retrieved |
| `RAG_MIN_CONFIDENCE_SCORE` | `0.55` | Abstention threshold |
| `RAG_ENABLE_HYBRID_RETRIEVAL` | `true` | Hybrid vs vector-only |
| `RAG_ENABLE_UNKNOWN_ANSWER` | `true` | Abstention on/off |
| `RAG_ENABLE_CITATIONS` | `true` | Return sources |
| `RAG_VECTOR_WEIGHT` / `RAG_KEYWORD_WEIGHT` | `0.7` / `0.3` | Fusion weights |

---

## Tests

```bash
pip install pytest sqlalchemy pydantic
pytest tests -v -m "not integration"
```

Unit tests cover hybrid retrieval scoring, citation formatting, the
unknown-answer decision, and tenant-isolation scoping. CI runs them on every
push (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

---

## Roadmap

- [ ] **JWT authentication** to bind users to tenants
- [ ] **RBAC** for document- and action-level authorization
- [ ] **Kubernetes** manifests + Helm chart for production deployment
- [ ] **HANA Vector adapter** (pluggable vector store interface)
- [ ] **OpenTelemetry** traces/metrics export
- [ ] **RAGAS** integration for richer offline evaluation
- [ ] Streaming (SSE) responses and per-file chat scoping

---

## Resume Bullets

- Designed and built a **multi-tenant RAG reference architecture** (FastAPI,
  React, PostgreSQL/pgvector) with strict per-tenant data isolation enforced at
  the database layer.
- Implemented **hybrid retrieval** (weighted vector + keyword fusion) with a
  confidence-gated **abstention** path, eliminating ungrounded answers.
- Engineered **grounded generation with citations** and a structured **response
  contract** (answer, sources, confidence, latency, token usage) for full
  auditability.
- Added an **offline evaluation harness** (citation rate, groundedness,
  unknown-answer accuracy) and **observability** instrumentation, wired into
  **CI**.

---

## Why a Reference Architecture?

This project is a reusable reference architecture that codifies
**responsible, grounded, multi-tenant RAG** patterns — applicable across
enterprises adopting LLM systems. It emphasizes the durable engineering
concerns (isolation, evaluation, observability, abstention) rather than a
single application, so teams can adapt the patterns to their own stack.

---

## License

MIT.
