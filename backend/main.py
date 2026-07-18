import os
import sys

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import database
import rag_service
import news_service
import discovery_service
import scheduler

app = FastAPI(title="AI Atlas Platform API", version="1.0.0")

# Enable CORS for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event: Ingest DB and build FAISS index
@app.on_event("startup")
def on_startup():
    # If custom DATABASE_PATH is defined and database does not exist, copy the pre-seeded DB file
    custom_db_path = os.environ.get("DATABASE_PATH")
    if custom_db_path and not os.path.exists(custom_db_path):
        print(f"Custom database path {custom_db_path} does not exist.")
        db_dir = os.path.dirname(custom_db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        seeded_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas.db")
        if os.path.exists(seeded_path):
            import shutil
            print(f"Copying pre-seeded database from {seeded_path} to {custom_db_path}...")
            shutil.copy2(seeded_path, custom_db_path)
        else:
            print("Pre-seeded database file not found. Creating empty database.")

    database.init_db()
    try:
        # Build FAISS index on startup
        rag_service.build_faiss_index()
    except Exception as e:
        print(f"FAISS index build deferred on startup: {e}. (Awaiting GEMINI_API_KEY)")
        
    # Start news refresh scheduler
    scheduler.start_scheduler()

# --- Pydantic Schemas ---

class QueryModel(BaseModel):
    query: str

class CompanyModel(BaseModel):
    name: str
    country: str
    ai_category: Optional[str] = ""
    seg_tags: Optional[str] = ""
    germany_presence: Optional[str] = ""
    company_type: Optional[str] = ""
    use_cases: Optional[str] = ""
    customers: Optional[str] = ""
    funding: Optional[str] = ""
    revenue: Optional[str] = ""
    maturity: Optional[str] = ""
    deployment_evidence: Optional[str] = ""
    website: Optional[str] = ""

class DiscoverModel(BaseModel):
    sector: str
    country: str

class WatchlistToggleModel(BaseModel):
    company_id: int

# --- API Endpoints ---

@app.get("/api/companies")
def get_companies(
    search: Optional[str] = None,
    segment: Optional[int] = None,
    company_type: Optional[str] = None,
    maturity: Optional[str] = None
):
    try:
        return database.get_companies(search, segment, company_type, maturity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/companies/{company_id}")
def get_company(company_id: int):
    comp = database.get_company(company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Company not found")
    return comp

@app.post("/api/companies")
def add_company(company: CompanyModel, background_tasks: BackgroundTasks):
    try:
        new_id = database.add_company(company.dict())
        # Rebuild FAISS index in the background
        background_tasks.add_task(rag_service.build_faiss_index)
        return {"success": True, "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/companies/{company_id}")
def update_company(company_id: int, company: CompanyModel, background_tasks: BackgroundTasks):
    try:
        success = database.update_company(company_id, company.dict())
        if not success:
            raise HTTPException(status_code=404, detail="Company not found or no changes made")
        # Rebuild FAISS index in the background
        background_tasks.add_task(rag_service.build_faiss_index)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/companies/{company_id}/news/refresh")
def refresh_company_news(company_id: int, background_tasks: BackgroundTasks):
    # Fetch news on-demand (synchronously here, to give instant feedback on the UI)
    try:
        added_count = news_service.fetch_news_for_company(company_id)
        # Rebuild FAISS index is already called inside fetch_news_for_company if items are added
        return {"success": True, "added_count": added_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sectors")
def get_sectors():
    try:
        return database.get_sectors()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/problems")
def get_problems():
    try:
        return database.get_problems()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news")
def get_all_news(limit: int = 50):
    try:
        return database.get_all_news(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ask")
def ask_assistant(payload: QueryModel):
    try:
        return rag_service.ask_ai(payload.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/discover")
def discover_companies(payload: DiscoverModel):
    res = discovery_service.discover_companies(payload.sector, payload.country)
    if not res.get("success", False):
        raise HTTPException(status_code=500, detail=res.get("error", "AI Discovery failed"))
    return res

@app.post("/api/admin/approve-company")
def approve_company(company: CompanyModel, background_tasks: BackgroundTasks):
    try:
        new_id = database.add_company(company.dict())
        # Rebuild FAISS index in background
        background_tasks.add_task(rag_service.build_faiss_index)
        
        # Trigger immediate news search for approved company in the background
        background_tasks.add_task(news_service.fetch_news_for_company, new_id)
        
        return {"success": True, "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/watchlist/toggle")
def toggle_watchlist(payload: WatchlistToggleModel):
    try:
        added = database.toggle_watchlist(payload.company_id)
        return {"success": True, "added": added}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/watchlist")
def get_watchlist():
    try:
        return database.get_watchlist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Setup frontend static files serving
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if not os.path.exists(frontend_dir):
    os.makedirs(frontend_dir)

app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
