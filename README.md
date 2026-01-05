# Enterprise RAG Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-green)](https://www.docker.com/)
[![Status](https://img.shields.io/badge/status-active_development-orange)]()

A scalable, production-ready **Retrieval-Augmented Generation (RAG)** system designed for enterprise data. This platform handles the end-to-end pipeline: from document ingestion and chunking to vector storage and context-aware LLM generation.

---

## 🚀 Key Features

* **Contextual Query Rewriting**: Uses an intermediary LLM step to rephrase user queries, resolving ambiguities and chat history context *before* retrieval for higher accuracy.
* **Multi-Format Ingestion**: Support for PDF, DOCX, TXT, and Markdown files with robust text extraction.
* **Advanced Chunking Strategies**: Semantic and token-based splitting to maximize retrieval context.
* **Vector Database Integration**: Modular support for vector stores (Qdrant, Pinecone, or Milvus).
* **LLM Agnostic**: Plug-and-play architecture for OpenAI, Anthropic, or local open-source models (via Ollama/vLLM).
* **Hybrid Search**: Combines dense vector search with keyword-based (sparse) search.
* **API-First Design**: RESTful API endpoints built for seamless frontend integration.
* **Containerized**: Fully Dockerized for consistent deployment across environments.

---

## 🛠️ Tech Stack

* **Language**: Python 3.10+
* **Framework**: FastAPI / Flask (configurable)
* **Orchestration**: LangChain / LlamaIndex
* **Database**: Qdrant (Vector Store), PostgreSQL (Metadata)
* **Containerization**: Docker & Docker Compose
* **CI/CD**: GitHub Actions

---

## 🏗️ Architecture

The platform follows a microservice-like architecture:

1.  **Ingestion Service**: Parses documents, cleans data, and updates metadata.
2.  **Embedding Service**: Converts text chunks into vector embeddings.
3.  **Query Transformation Service**:
    * *Contextual Rewriting*: Reformulates the user's raw prompt into a standalone search query.
    * *Query Expansion*: Generates multiple variations of the query to broaden search coverage.
4.  **Retrieval Service**: Performs hybrid similarity search against the Vector DB using the transformed query.
5.  **Generation Service**: Synthesizes the answer using the LLM and retrieved context.

---

## ⚡ Getting Started

### Prerequisites

* Docker & Docker Compose
* Python 3.10+ (for local development)
* API Keys (OpenAI, Anthropic, etc.)

### Installation

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/pallavi-chandrashekar/enterprise-rag-platform.git](https://github.com/pallavi-chandrashekar/enterprise-rag-platform.git)
    cd enterprise-rag-platform
    ```

2.  **Set up Environment Variables**
    Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
    *Update `.env` with your API keys and configuration preferences.*

3.  **Run with Docker (Recommended)**
    ```bash
    docker-compose up --build -d
    ```

4.  **Run Locally (Dev Mode)**
    ```bash
    pip install -r requirements.txt
    python main.py
    ```

---

## 📖 Usage

### API Endpoints

Once the server is running (default: `http://localhost:8000`), you can access the Swagger UI documentation at `/docs`.

#### 1. Ingest Documents
**POST** `/api/v1/ingest`
```json
{
  "file_path": "./data/quarterly_report.pdf",
  "metadata": {"department": "finance"}
}

```

#### 2. Query (Chat) with Strategies
**POST** `/api/v1/chat`

You can now specify a search strategy to optimize retrieval for different types of questions.

```json
{
  "query": "Compare the Q3 and Q4 revenue reports",
  "collection_name": "finance_docs",
  "strategy": "decomposition" 
}

```

| Strategy | Best For | Description |
| :--- | :--- | :--- |
| `simple` | Simple lookups | Standard hybrid search (Vector + Keyword). Default. |
| `multi_query` | Broad topics | Generates 3 variations of the question to catch synonyms. |
| `decomposition` | Complex comparisons | Breaks one complex question into sub-questions (e.g., "Compare X and Y" becomes "What is X?", "What is Y?"). |
| `hyde` | Technical/Fact-finding | Generates a hypothetical answer first, then searches for matching vector patterns. |

*Note: The system will use the history to rewrite the query to "compare Q4 revenue to Q3 revenue" before searching.*

---

## 🗺️ Roadmap

* [x] Basic Document Ingestion (PDF/TXT)
* [x] Vector Database Connection
* [x] Contextual Query Rewriting
* [ ] Add Re-ranking (Cross-Encoders)
* [ ] Implement Persistent Chat History / Memory
* [ ] User Authentication (OAuth2)
* [ ] Frontend UI (React/Next.js)

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the project.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

**Built with ❤️ by [Pallavi Chandrashekar**](https://github.com/pallavi-chandrashekar)
