# Responsible AI

This reference architecture treats responsible AI as an engineering
requirement, not an afterthought. The controls below are implemented in code,
not just documented.

## Tenant Isolation

- Every document, chunk, and chat session is owned by a `tenant_id`.
- All retrieval and read queries include a `tenant_id` predicate at the SQL
  layer; there is no code path that returns one tenant's data to another.
- Requests are scoped via the `X-Tenant-ID` header (and `tenant_id` in the
  search payload). Authentication/authorization to *bind* a user to a tenant is
  on the roadmap (JWT + RBAC).

## Grounded Answers

- Retrieval-augmented answers are generated with a system prompt that instructs
  the model to use **only** the supplied context and to cite sources.
- The model is run at low temperature to reduce fabrication.
- Generation never falls back to ungrounded "general knowledge" for document
  questions.

## Citations

- When enabled (`RAG_ENABLE_CITATIONS`), every grounded answer returns the
  chunks it drew from: document, filename, chunk index, snippet, and the
  vector / keyword / combined scores.
- This makes answers auditable — a reviewer can trace each answer back to
  source text.

## Unknown-Answer Handling (Abstention)

- When there are no relevant chunks, or retrieval confidence is below
  `RAG_MIN_CONFIDENCE_SCORE`, the system returns
  *"I don't know based on the available documents."* instead of guessing.
- If the model itself abstains, citations are dropped so the UI does not imply
  false grounding.

## Minimal Logging / Data Handling

- Observability logs record metadata (tenant, mode, counts, latency, tokens),
  **not** raw answer text or document contents.
- Raw uploaded files are parsed and chunked at ingestion; the architecture does
  not require retaining original files.
- Configuration secrets (API keys) are supplied via environment variables and
  excluded from version control (`.gitignore`, `.env.example`).

## Limitations & Honest Disclosure

- The groundedness metric is a lexical proxy, not a full NLI/entailment judge.
- Confidence is a retrieval-score proxy, not a calibrated probability.
- The default embedding model is small and English-centric; evaluate before
  using on multilingual or highly specialized corpora.

These limitations are intentionally surfaced so downstream users can make
informed decisions rather than over-trusting the system.
