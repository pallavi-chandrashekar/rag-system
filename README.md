# 🏢 Multi-Tenant Enterprise RAG Platform

A production-ready, multi-tenant Retrieval-Augmented Generation (RAG) system built with **FastAPI**, **React**, **PostgreSQL (pgvector)**, and **OpenAI**.

This platform features an **Agentic Router** that automatically detects user intent (Greetings vs. Summarization vs. Deep Search) and supports full **Chat Session Management** with strict data isolation between tenants.

![Project Status](https://img.shields.io/badge/status-production--ready-green) ![License](https://img.shields.io/badge/license-MIT-blue)

## ✨ Key Features

### 🧠 Intelligent Agent (Auto-Router)
- **Intent Detection:** Automatically classifies queries into strategies:
  - `LLM_ONLY`: For greetings and general knowledge (e.g., "Hi", "What is Python?").
  - `SUMMARY`: Bypasses vector search to read raw document chunks for full overviews.
  - `SEARCH`: Performs vector similarity search for specific questions.
- **Fail-Safe Fallback:** If the vector database returns zero results, the system automatically falls back to the LLM's general knowledge.

### 🔐 Enterprise Security
- **Multi-Tenancy:** Strict data isolation. `Tenant A` cannot access documents or chat history belonging to `Tenant B`.
- **Tenant Scoping:** All API requests are scoped via the `X-Tenant-ID` header.

### 📂 Advanced Ingestion
- **PDF Parsing:** Integrated `pypdf` extraction to handle complex PDF layouts.
- **Smart Chunking:** Sentence-aware text splitting (`RecursiveCharacterTextSplitter` logic) to preserve semantic context.

### 💬 Session Management
- **Persistent History:** Conversations are saved to PostgreSQL (`chat_sessions` table).
- **Context Menu:** Right-click sidebar items to **Rename** or **Delete** specific chat sessions.
- **Auto-Restore:** Automatically loads the most recent conversation upon browser refresh.

---

## 🏗️ Architecture

The system uses a **Router-Based RAG** architecture. The "Brain" (Router) decides the best tool for the job before any search happens.

```mermaid
graph TD
    %% -- Client Layer --
    User[User / React UI] -->|Sends Query + TenantID| API[FastAPI Backend]

    %% -- Application Layer --
    subgraph Backend Services
        API --> Router{Router Agent}
        
        %% Strategy 1: General Chat
        Router -- "Hi / General" --> LLM_Only[LLM Direct Chat]
        
        %% Strategy 2: Summarization
        Router -- "Summarize" --> DB_Raw[Fetch Raw Content]
        DB_Raw --> LLM_Sum[LLM Summarizer]
        
        %% Strategy 3: Search (RAG)
        Router -- "Complex Query" --> Embed[Embedding Model]
        Embed --> VectorSearch[Vector Search]
        VectorSearch --> Rerank[Context Assembly]
        Rerank --> LLM_RAG[LLM Answer Gen]
    end

    %% -- Data Layer --
    subgraph Database [PostgreSQL]
        VectorDB[(pgvector: Chunks)]
        SessionDB[(Table: Chat_Sessions)]
    end

    %% -- Connections --
    VectorSearch <--> VectorDB
    DB_Raw <--> VectorDB
    
    %% -- History Management --
    API -->|Save History| SessionDB
    SessionDB -->|Load History| API

    %% -- External AI --
    LLM_Only <--> OpenAI
    LLM_Sum <--> OpenAI
    LLM_RAG <--> OpenAI

```

---

## 🛠️ Tech Stack

| Component | Technology | Description |
| --- | --- | --- |
| **Frontend** | React + Vite | Fast, modern UI with Sidebar and Context Menus. |
| **Backend** | FastAPI (Python) | High-performance async API. |
| **Database** | PostgreSQL | Relational data + `pgvector` for embeddings. |
| **ORM** | SQLAlchemy | Database interaction and model management. |
| **AI / LLM** | OpenAI GPT-4o | Intelligence layer (Routing & Generation). |
| **Ingestion** | pypdf | Robust PDF text extraction. |

---

## 🚀 Quick Start

### 1. Prerequisites

* **Docker** & **Docker Compose** installed.
* An **OpenAI API Key**.

### 2. Configuration

Create a `.env` file or update your `docker-compose.yml` directly:

```yaml
services:
  rag-backend:
    environment:
      - DATABASE_URL=postgresql://user:password@rag-db:5432/ragdb
      - OPENAI_API_KEY=sk-proj-YOUR-ACTUAL-KEY-HERE  # <--- Required

```

### 3. Build & Run

```bash
# Stop any existing containers
docker-compose down

# Build and start the system
docker-compose up -d --build

```

### 4. Access the App

* **Frontend:** [http://localhost:5173](https://www.google.com/search?q=http://localhost:5173)
* **API Documentation:** [http://localhost:8000/docs](https://www.google.com/search?q=http://localhost:8000/docs)

---

## 📖 Usage Guide

### 1. Managing Tenants

* Enter a **Tenant ID** (e.g., `demo-corp`) in the sidebar.
* The system creates a virtual wall; documents uploaded here are invisible to other Tenant IDs.

### 2. Ingesting Documents

* Click the **"Upload File"** area in the sidebar.
* Select a `.pdf` or `.txt` file.
* The system parses, chunks, embeds, and stores it in seconds.

### 3. Chat Modes

* **General Chat:** Type *"Hi"* or *"How are you?"*. The Agent skips the database and replies instantly.
* **Summarization:** Type *"Summarize this document"*. The Agent pulls raw text chunks and generates a summary.
* **Deep Search:** Ask a specific question (e.g., *"What is the revenue for Q3?"*). The Agent performs a vector search.

### 4. Managing Sessions

* **New Chat:** Click the `+ New Chat` button to start fresh.
* **Rename:** Right-click a chat in the history list -> Select **Rename**.
* **Delete:** Right-click a chat -> Select **Delete** to wipe it from the database.

---

## 🔮 Future Roadmap

* [ ] **Authentication:** Replace manual Tenant ID entry with JWT Login.
* [ ] **OCR Support:** Integrate `pytesseract` for scanned image PDFs.
* [ ] **Streaming:** Implement Server-Sent Events (SSE) for typewriter-style responses.
* [ ] **File Filtering:** Allow users to chat with a *specific* file only.

## 🛡️ License

This project is licensed under the MIT License.
