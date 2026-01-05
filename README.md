# Enterprise RAG Platform

A production-ready Retrieval-Augmented Generation (RAG) system built for high-accuracy enterprise use cases. This platform moves beyond simple vector search by implementing **Hybrid Search (Vector + Keyword)** and **Reciprocal Rank Fusion (RRF)** to solve common RAG failure modes like vocabulary mismatch and exact-match prioritization.

## 🚀 Key Features

* **Hybrid Search Architecture:** Combines semantic understanding (Vector Search via `pgvector`) with exact-match precision (Keyword Search).
* **Reciprocal Rank Fusion (RRF):** Intelligently re-ranks results to balance semantic relevance with keyword specificity.
* **Multi-Tenancy:** logical data isolation using `tenant_id` at the database level.
* **PostgreSQL Native:** Uses `pgvector` to keep the tech stack simple and compliant (no external vector DB required).
* **Automated Evaluation Suite:** Includes scenario-based testing scripts to verify RAG performance against edge cases.

## 🛠️ Tech Stack

* **Language:** Python 3.11+
* **Framework:** FastAPI (Async)
* **Database:** PostgreSQL 16 (with `pgvector` extension)
* **LLM/Embeddings:** OpenAI API (configurable)
* **Containerization:** Docker & Docker Compose
* **Testing:** Pytest & Custom Scenario Scripts

## 🏗️ Architecture

The system uses a **Retrieval-Re-ranking** pipeline:

1.  **Ingestion:** Documents are chunked, embedded (OpenAI `text-embedding-3-small`), and stored in Postgres.
2.  **Querying:**
    * **Path A (Vector):** Cosine similarity search for semantic meaning.
    * **Path B (Keyword):** SQL `ILIKE` / Full-Text Search for specific terminology.
3.  **Fusion:** Results from Path A and B are fused using the **RRF Algorithm** ($$score = \frac{1}{k + rank}$$).
4.  **Generation:** The top fused contexts are sent to the LLM to generate the final answer.

## ⚡ Getting Started

### Prerequisites
* Docker & Docker Compose
* OpenAI API Key

### Installation

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/pallavi-chandrashekar/enterprise-rag-platform.git](https://github.com/pallavi-chandrashekar/enterprise-rag-platform.git)
    cd enterprise-rag-platform
    ```

2.  **Set Environment Variables**
    Create a `.env` file in the root directory:
    ```bash
    DATABASE_URL=postgresql://user:password@rag_db:5432/ragdb
    OPENAI_API_KEY=your_sk_key_here
    ```

3.  **Run with Docker**
    ```bash
    docker-compose up --build
    ```
    The API will be available at `http://localhost:8000`.

## 📖 Usage API

### 1. Ingest Documents
Upload text files (PDF parsing coming soon) to the vector store.

```bash
curl -X 'POST' \
  'http://localhost:8000/ingest?tenant_id=demo-tenant' \
  -F 'file=@./data/policy.txt'

### 2. Query (Hybrid Search)
Ask a question. The system will automatically balance vector and keyword results.

```bash
curl -X 'POST' \
  'http://localhost:8000/rag/query' \
  -H 'Content-Type: application/json' \
  -d '{
  "query": "What is the refund policy?",
  "tenant_id": "demo-tenant",
  "top_k": 5
}'

🧪 Testing & Evaluation
This project includes a Scenario-Based Testing Suite (tests/test_scenarios.py) that validates the system against common RAG failure modes.

Run the Evaluation
```bash
# Ensure the stack is running, then:
python tests/test_scenarios.py

Test Scenarios Covered

### Test Scenarios Covered

| Scenario | Challenge | Success Criteria |
| :--- | :--- | :--- |
| **Vocabulary Mismatch** | User asks "connection drops" vs Doc says "network failure" (no shared words). | Vector search must retrieve the correct document based on semantic meaning alone. |
| **Exact Keyword Override** | User asks for specific "Error 505" vs generic "Error 500" documents. | Keyword search must prioritize the exact match ("505") over the generic vector match. |
| **Conflicting Info** | Database contains an old 2020 policy and a new 2025 policy. | System must retrieve *both* documents so the LLM has the full context to answer correctly. |


🔮 Roadmap
[ ] Integration with DeepEval for LLM-as-a-Judge metrics.

[ ] Advanced Chunking (Semantic Chunking).

[ ] Admin UI for managing tenants and documents.