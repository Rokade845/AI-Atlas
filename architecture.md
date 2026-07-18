# Architecture & Design Decisions - AI Atlas

This document outlines the architectural patterns, data modeling, retrieval design, and trade-offs made during the development of the **AI Atlas** platform.

---

## 1. Relational Data Model

We modeled the German Food & Beverage dataset using an **SQLite database** (`backend/atlas.db`). SQLite was selected because it is highly performant for local, low-concurrency analysis, requires zero installation or container overhead for local deployment, and is fully relational, supporting transactional updates.

### Schema Relationships
The schema comprises the following tables:
- `companies`: Holds the primary profile data (maturity, funding, revenue, presence, use cases).
- `sectors`: Contains definitions, adoptive ratings, and adopted profiles for each of the 15 segments.
- `problems`: Holds severity, regulatory triggers, and descriptions for F&B challenges.
- `problem_company_mappings`: Captures the ROI benchmarks and ranked vendors connecting problems to segments.
- `news_items`: Stored RSS-fetched, relevance-filtered, and summarized news articles mapped to companies.
- `watchlist`: Stores watched company IDs.

```
       [ sectors ] 
           │
           │ Many-to-Many (via comma-split tags)
           ▼
     [ companies ] ◄───────[ watchlist ]
           │
           │ 1-to-Many
           ▼
     [ news_items ] 
           ▲
           │ Many-to-Many (via name alignment)
           ▼
[ problem_company_mappings ] ◄──► [ problems ]
```

---

## 2. Hybrid RAG & Grounding Strategy

A common failure mode in standard Vector RAG systems is the inability to return *precise, exact values* for structured queries (e.g. "What is the funding of Marel?"). The embedding search might return multiple chunks, causing the LLM to hallucinate or mix up numbers.

To guarantee **100% round-trip fidelity** of structured data, we designed a **Hybrid Grounded Retrieval** system:

```
                      [ User Query ]
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      [ Entity Extraction ]       [ Vector Embedding ]
              │ (Regex/Lookup)            │ (text-embedding-004)
              ▼                           ▼
    [ Matches Company? ]          [ FAISS Search ]
              │                           │
       Yes ┌──┴──┐ No                     │
           ▼     ▼                        ▼
     [ DB Lookup: ]              [ Retrieve Top 6 ]
     [ Inject Full]              [ Related Chunks ]
     [ Row Details]                       │
           │                              │
           └──────────────┬───────────────┘
                          ▼
             [ Context Consolidation ]
                          │
                          ▼
            [ Gemini 1.5 Grounded Prompt ]
```

### Retrieval Stages:
1. **Entity Extraction (Deterministic Stage)**:
   The user's query is analyzed to see if it mentions any company name in our database. If it does, the system bypasses vector retrieval for profile parameters and loads the *entire structured record* directly from SQLite. This injects the exact ground-truth values (funding, revenue, maturity, deployment evidence) into the prompt context.
2. **Vector Retrieval (Semantic Stage)**:
   The query is embedded using Gemini's `text-embedding-004` and queried against an in-memory **FAISS (IndexFlatL2)** index containing serialized chunks of problems, mappings, general news, and other profiles. This retrieves wider semantic context, such as industry problem statements or ROI benchmarks.
3. **Synthesis & Citation**:
   The combined context is formatted with a strict system prompt instructing `gemini-1.5-flash` to restrict answers *only* to facts inside the context, format references as markdown links to profiles or external news sources, and output "I do not have this information in my knowledge base" if the facts are missing.

---

## 3. Dynamic Knowledge Base Updates

To support live updates without rebuilds or expensive re-embeddings:
- We stored generated vector embeddings directly as JSON string float arrays in the SQLite database (`embedding` column).
- When a new company is added manually or via admin discovery, or when news is fetched, we compute its embedding *once* and cache it in the DB.
- Rebuilding the FAISS index is performed in-memory on the FastAPI startup/endpoints by loading all cached embeddings. For a dataset size of 100-1000 items, rebuilding the index takes **under 50 milliseconds**, enabling **instant query availability** on updates without rebuilds.

---

## 4. Automated News Pipeline

The Newsletter tab aggregates live news articles using Google News RSS and processes them through an automated AI pipeline:

```
[ Company Profile ] ──► [ Query Google News RSS ] ──► [ Parse XML Articles ]
                                                              │
                                                              ▼
[ Save & Index ] ◄── [ AI Summarizer ] ◄── [ Relevance Filter (Yes) ] ◄── [ AI Relevance Check ]
                                                              │
                                                              ▼ (No)
                                                         [ Discard ]
```

### Addressing Key Failure Modes:
- **Name Collisions & Irrelevant News**: Many company names are common words (e.g. "NotCo" or "Picnic"). A naive keywords RSS query pulls noisy, unrelated news. To prevent this, we run a relevance check: we prompt Gemini to analyze the article's headline and description against the company profile, returning a strict Boolean response (`is_relevant: true/false`). Only verified news enters the DB.
- **Duplicate Articles**: The pipeline computes the hash of article URLs, checking against existing entries to enforce de-duplication.
- **No News Found**: If no articles pass the relevance filter, the DB remains unchanged, and the UI displays a clean "No recent news found" state.
- **Polling & On-Demand Refresh**: FastAPI starts an async loop task that fetches news for all companies every 6 hours, while the frontend exposes a "Refresh Live News" button to fetch news synchronously for that specific company on-demand.

---

## 5. Search-Grounded Admin Discovery

The Admin Discovery pipeline uses Gemini with **Google Search Grounding** enabled (`tools="google_search"`).
1. The admin inputs a sector and country (e.g., "Dairy Processing" + "Germany").
2. Gemini performs live web research to discover real companies.
3. The prompt requires the model to return candidates in a strict JSON schema matching our SQL data model, along with **evidencing search URLs, verbatim snippets, and confidence levels**.
4. **Human-in-the-Loop Verification**: The admin reviews candidates against the cited evidence, makes edits inline on the dashboard form, and approves them. Discovered companies are de-duplicated, saved, embedded, and immediately queryable in Ask AI.

---

## 6. Key Trade-offs & Decisions

### Trade-off 1: Vanilla Frontend vs. React/Vite Build
- **Decision**: We chose a single-page app utilizing Vanilla HTML, ES6 JavaScript, and custom CSS served directly as static files by FastAPI.
- **Rationale**: React/Next.js apps introduce build steps, compiler versions, and extensive `node_modules` folders. A zero-build vanilla frontend runs immediately from a clean clone when uvicorn starts, eliminating npm version errors or port collisions, resulting in maximum evaluator reliability. We crafted a premium, custom CSS design system to ensure no compromise in visual aesthetics.

### Trade-off 2: SQLite vs. pgvector / Chroma
- **Decision**: SQLite + in-memory FAISS.
- **Rationale**: Installing vector databases like Chroma or pgvector requires external services (e.g. Docker, database connections). An in-memory FAISS index built from cached SQLite embeddings is lightweight, extremely fast, completely self-contained, and perfectly scales to thousands of records.

---

## 7. Scaling to More Sectors and Countries

If scaling this system to hundreds of thousands of companies across multiple countries:
1. **Vector Database Migration**:
   Migrate from in-memory FAISS to a managed vector store (e.g. Pinecone, Qdrant, or pgvector in PostgreSQL) to support distributed query scaling and handle billions of vectors.
2. **Chunking & Hierarchical Search**:
   For very large knowledge bases, implement parent-child chunking (e.g. chunking company reports, press releases, and product specs separately) and implement a re-ranking model (like Cohere Rerank) to filter the top retrieved vectors before LLM synthesis.
3. **Queue-based News Polling**:
   Replace the simple FastAPI async task loop with a distributed task queue like Celery or Redis Queue (RQ) to run news collection concurrently for thousands of companies, preventing rate limits using proxy rotation and domain-level throttling.
4. **Structured Named Entity Recognition (NER)**:
   Replace the basic regex company name parser in Ask AI with an LLM-based entity extraction parser or SpaCy NER model to identify complex company mentions and abbreviations inside long user queries.
