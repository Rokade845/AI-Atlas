# AI Atlas — Intelligence Platform with Ask AI & Automated News

AI Atlas is an intelligence platform indexing companies, problems, and value chains where Artificial Intelligence is deployed in the German Food & Beverage (F&B) sector.

This application is built with a **FastAPI backend** (Python) and a **Vanilla HTML/CSS/JS frontend**, utilizing **SQLite** for relational storage and **FAISS** for grounded RAG (Retrieval-Augmented Generation) search with Gemini.

---

## Technical Stack
- **LLM Provider**: Gemini (`gemini-1.5-flash` for answering/filtering and `text-embedding-004` for vector embeddings).
- **Vector Search**: FAISS in-memory index built dynamically from SQLite caches.
- **Relational Database**: SQLite (built-in, zero configuration, highly portable).
- **News Aggregator**: Google News RSS feed with Gemini-based relevance filtering and automated one-sentence summarization.
- **Scheduling**: Asyncio background worker executing automated news updates.
- **Frontend**: Zero-build single-page web dashboard using HTML, ES6 JavaScript, and custom CSS (Glassmorphism layout).

---

## Project Structure
```
ai_atlas/
├── atlas_dataset/           # Mandatory CSV datasets
│   ├── companies_germany.csv
│   ├── problems_germany.csv
│   ├── problem_company_mapping.csv
│   └── sectors_reference.csv
├── backend/                 # FastAPI backend application
│   ├── .env.example         # Example configuration
│   ├── .env                 # Active configuration (user created)
│   ├── atlas.db             # Seeded SQLite database (after ingestion)
│   ├── db_init.py           # Seeding & Ingestion script
│   ├── database.py          # Relational CRUD queries
│   ├── rag_service.py       # FAISS indexing & hybrid search retrieval
│   ├── news_service.py      # RSS News parser & Gemini filters
│   ├── discovery_service.py # Search Grounded Company Discovery
│   ├── scheduler.py         # News background polling scheduler
│   ├── requirements.txt     # Python dependencies
│   └── main.py              # Server entry point & API endpoints
├── frontend/                # Single Page App dashboard
│   ├── index.html           # Layout
│   ├── style.css            # Custom CSS styling
│   └── app.js               # Event handlers & DOM updates
├── README.md                # This file
└── architecture.md          # Architecture & Design Decisions
```

---

## Installation & Setup

### 1. Prerequisites
Ensure you have **Python 3.10+** installed on your system.

### 2. Create Virtual Environment & Install Dependencies
Run the following commands in the project root directory:

```bash
# Initialize virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables
Create a file named `.env` in the `backend/` directory:

```bash
touch backend/.env
```

Add your Gemini API Key and configuration details inside `backend/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
PORT=8000
HOST=0.0.0.0
```

---

## Ingestion & DB Seeding
To parse the provided CSV files and seed the SQLite relational database, run:

```bash
python backend/db_init.py
```

*Output should indicate:*
```
Ingesting sectors...
Ingesting companies...
Ingesting problems...
Ingesting problem-company mappings...
Database ingestion completed successfully!
```

---

## Starting the Application
Start the FastAPI server using the uvicorn runner inside the virtual environment:

```bash
# Run server from project root
venv/bin/uvicorn backend.main:app --reload --port 8000
```

Once running, open your web browser and navigate to:
**[http://localhost:8000](http://localhost:8000)**

---

## Verification & Testing Guide

1. **Company Directory & Filters**:
   - Browse the 116 F&B companies in the grid.
   - Filter by Sector segment pills (e.g. Dairy Processing, Meat Processing), Company Type (Incumbent/NewCo), or Maturity rating.
   
2. **Tabbed Company Profiles**:
   - Click on any company card to open its profile slide-over panel.
   - **Overview Tab**: Displays funding, revenue, maturity, and use cases.
   - **Problems Solved Tab**: Displays severity-sorted problems this company addresses, featuring explicit ROI benchmarks.
   - **Newsletter Tab**: Fetches live, relevant news. Click **"Refresh Live News"** to aggregate on-demand news filtered and summarized by Gemini.

3. **Grounded Ask AI Chatbot**:
   - Navigate to the **Ask AI** tab on the sidebar.
   - Send questions (e.g. *"What is the revenue and maturity of GEA Group AG?"*).
   - Chat answers display source citations. Click company links (e.g. `[GEA Group AG](/#/company/2)`) to jump directly to their profile pages.

4. **AI-Powered Admin Discovery**:
   - Navigate to **Admin Dashboard -> AI Company Discovery**.
   - Input a sector (e.g. *"Brewery AI"*) and country (e.g. *"Germany"*).
   - Review proposed candidate details, web evidence links, snippets, and confidence levels.
   - Modify fields, approve them to ingest into the active DB, and verify that the company immediately appears in the directory and Ask AI searches.
