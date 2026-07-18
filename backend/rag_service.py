import os
import sys

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
import sqlite3
import numpy as np
import faiss
import google.generativeai as genai
from database import get_db_connection, update_embedding

# Custom env loader
def load_env():
    # Try current directory or parent directory for .env
    for path in [".env", "backend/.env", "../backend/.env"]:
        abs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), path)
        if os.path.exists(abs_path):
            with open(abs_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            k, v = parts[0].strip(), parts[1].strip()
                            if k and v and k not in os.environ:
                                os.environ[k] = v
            break

load_env()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Global in-memory index variables
faiss_index = None
indexed_items = [] # list of dicts mapping index rows to DB entities

def get_gemini_client():
    global GEMINI_API_KEY
    if not GEMINI_API_KEY:
        # Retry loading env in case it was written later
        load_env()
        GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
    return bool(GEMINI_API_KEY)

def get_embedding(text):
    """Call Gemini to get embedding for a text chunk."""
    if not get_gemini_client():
        raise ValueError("GEMINI_API_KEY is not configured. Please set it in backend/.env")
    
    response = genai.embed_content(
        model="models/gemini-embedding-2",
        content=text,
        task_type="retrieval_document"
    )
    return response['embedding']

def get_query_embedding(query):
    """Get query embedding for vector search."""
    if not get_gemini_client():
        raise ValueError("GEMINI_API_KEY is not configured. Please set it in backend/.env")
        
    response = genai.embed_content(
        model="models/gemini-embedding-2",
        content=query,
        task_type="retrieval_query"
    )
    return response['embedding']

def build_faiss_index():
    """Load all records, generate embeddings (if not cached), and build FAISS index."""
    global faiss_index, indexed_items
    
    print("Building/Rebuilding FAISS index...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    items = []
    
    # 1. Fetch companies
    companies = cursor.execute("""
        SELECT id, name, country, ai_category, seg_tags, germany_presence, company_type, 
               use_cases, customers, funding, revenue, maturity, deployment_evidence, website, embedding 
        FROM companies
    """).fetchall()
    
    for c in companies:
        text = (
            f"Company Name: {c['name']}\n"
            f"Country / Presence: {c['germany_presence']} ({c['country']})\n"
            f"AI Category: {c['ai_category']}\n"
            f"Company Type: {c['company_type']}\n"
            f"F&B AI Use Cases: {c['use_cases']}\n"
            f"Top German Customers: {c['customers']}\n"
            f"Funding Stage: {c['funding']}\n"
            f"Estimated Revenue: {c['revenue']}\n"
            f"Maturity Level: {c['maturity']}\n"
            f"Deployment Evidence: {c['deployment_evidence']}\n"
            f"Website: {c['website']}"
        )
        
        vector = None
        if c['embedding']:
            try:
                vector = json.loads(c['embedding'])
            except Exception:
                pass
                
        if not vector and get_gemini_client():
            print(f"Generating embedding for company: {c['name']}")
            try:
                vector = get_embedding(text)
                update_embedding("companies", c['id'], vector)
            except Exception as e:
                print(f"Error embedding company {c['name']}: {e}")
                
        if vector:
            items.append({
                'type': 'company',
                'id': c['id'],
                'name': c['name'],
                'text': text,
                'vector': vector
            })
            
    # 2. Fetch problems
    problems = cursor.execute("""
        SELECT id, category, statement, seg_tags, severity, use_case_solution, 
               affected_companies, financial_impact, regulatory_trigger, problem_type, embedding 
        FROM problems
    """).fetchall()
    
    for p in problems:
        text = (
            f"Problem ID: {p['id']}\n"
            f"Category: {p['category']}\n"
            f"Problem Statement: {p['statement']}\n"
            f"Severity (1-5): {p['severity']}\n"
            f"AI Solution Use Case: {p['use_case_solution']}\n"
            f"Affected German Companies: {p['affected_companies']}\n"
            f"Financial Impact: {p['financial_impact']}\n"
            f"Regulatory Trigger: {p['regulatory_trigger']}\n"
            f"Problem Type: {p['problem_type']}"
        )
        
        vector = None
        if p['embedding']:
            try:
                vector = json.loads(p['embedding'])
            except Exception:
                pass
                
        if not vector and get_gemini_client():
            print(f"Generating embedding for problem: {p['id']}")
            try:
                vector = get_embedding(text)
                update_embedding("problems", p['id'], vector)
            except Exception as e:
                print(f"Error embedding problem {p['id']}: {e}")
                
        if vector:
            items.append({
                'type': 'problem',
                'id': p['id'],
                'name': p['statement'],
                'text': text,
                'vector': vector
            })
            
    # 3. Fetch problem mappings (benchmarks)
    mappings = cursor.execute("""
        SELECT id, problem_statement, seg_tags, vc_stage, ai_solution_1, ai_solution_2, 
               ai_solution_3, ranked_vendors, roi_benchmark, payback_months, regulatory_benefit, embedding 
        FROM problem_company_mappings
    """).fetchall()
    
    for m in mappings:
        text = (
            f"Problem Mapping: {m['problem_statement']}\n"
            f"AI Solution Options: {m['ai_solution_1']}, {m['ai_solution_2']}, {m['ai_solution_3']}\n"
            f"Ranked German Vendors: {m['ranked_vendors']}\n"
            f"ROI Benchmark: {m['roi_benchmark']}\n"
            f"Payback Period: {m['payback_months']} months\n"
            f"Regulatory Benefit: {m['regulatory_benefit']}"
        )
        
        vector = None
        if m['embedding']:
            try:
                vector = json.loads(m['embedding'])
            except Exception:
                pass
                
        if not vector and get_gemini_client():
            print(f"Generating embedding for mapping: {m['problem_statement'][:30]}...")
            try:
                vector = get_embedding(text)
                update_embedding("problem_company_mappings", m['id'], vector)
            except Exception as e:
                print(f"Error embedding mapping {m['id']}: {e}")
                
        if vector:
            items.append({
                'type': 'mapping',
                'id': m['id'],
                'name': m['problem_statement'],
                'text': text,
                'vector': vector
            })
            
    # 4. Fetch news items
    news = cursor.execute("""
        SELECT n.id, n.headline, n.source, n.publication_date, n.summary, n.url, c.name as company_name, n.embedding 
        FROM news_items n
        JOIN companies c ON n.company_id = c.id
    """).fetchall()
    
    for ns in news:
        text = (
            f"News Article for Company: {ns['company_name']}\n"
            f"Headline: {ns['headline']}\n"
            f"Source: {ns['source']} ({ns['publication_date']})\n"
            f"Summary: {ns['summary']}\n"
            f"URL: {ns['url']}"
        )
        
        vector = None
        if ns['embedding']:
            try:
                vector = json.loads(ns['embedding'])
            except Exception:
                pass
                
        if not vector and get_gemini_client():
            print(f"Generating embedding for news: {ns['headline'][:30]}...")
            try:
                vector = get_embedding(text)
                update_embedding("news_items", ns['id'], vector)
            except Exception as e:
                print(f"Error embedding news {ns['id']}: {e}")
                
        if vector:
            items.append({
                'type': 'news',
                'id': ns['id'],
                'name': ns['headline'],
                'text': text,
                'vector': vector
            })
            
    conn.close()
    
    if not items:
        print("No items to index.")
        faiss_index = None
        indexed_items = []
        return
        
    # Convert list of vectors to float32 numpy array
    vectors_array = np.array([x['vector'] for x in items], dtype=np.float32)
    dim = vectors_array.shape[1]
    
    # Initialize FAISS Index
    index = faiss.IndexFlatL2(dim)
    index.add(vectors_array)
    
    faiss_index = index
    indexed_items = [{
        'type': x['type'],
        'id': x['id'],
        'name': x['name'],
        'text': x['text']
    } for x in items]
    
    print(f"FAISS index built successfully with {len(items)} vectors!")

def search_index(query, k=5):
    """Vector search in FAISS index."""
    global faiss_index, indexed_items
    
    if faiss_index is None:
        build_faiss_index()
        
    if faiss_index is None:
        return []
        
    try:
        query_vec = np.array([get_query_embedding(query)], dtype=np.float32)
        distances, indices = faiss_index.search(query_vec, k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(indexed_items):
                results.append({
                    'item': indexed_items[idx],
                    'distance': float(distances[0][i])
                })
        return results
    except Exception as e:
        print(f"Search index failed: {e}")
        return []

def extract_mentioned_companies(query):
    """Find if a company name is mentioned in the query."""
    conn = get_db_connection()
    companies = conn.execute("SELECT id, name FROM companies").fetchall()
    conn.close()
    
    matches = []
    query_lower = query.lower()
    for c in companies:
        c_name = c['name'].lower()
        # Direct check or partial check for common name parts (excluding AG, GmbH, etc.)
        c_name_clean = c_name.replace(" ag", "").replace(" gmbh", "").replace(" se", "").replace(" co kg", "").replace("& co kg", "").strip()
        if c_name_clean in query_lower or c_name in query_lower:
            matches.append(dict(c))
            
    return matches

def ask_ai(query):
    """Answer natural language queries using hybrid search + Gemini."""
    if not get_gemini_client():
        return {
            "answer": "Gemini API key is not configured. Please set the `GEMINI_API_KEY` in the `backend/.env` file.",
            "sources": []
        }
        
    # 1. Direct Context Extraction (Entity-based)
    mentioned_companies = extract_mentioned_companies(query)
    direct_context = []
    sources = []
    
    conn = get_db_connection()
    
    for c in mentioned_companies:
        # Load the complete company profile with solved problems & news
        cursor = conn.cursor()
        company_row = cursor.execute("SELECT * FROM companies WHERE id = ?", (c['id'],)).fetchone()
        if company_row:
            company = dict(company_row)
            # Format detailed company text for 100% round-trip fidelity
            company_text = (
                f"### COMPANY PROFILE: {company['name']}\n"
                f"- **Country**: {company['country']}\n"
                f"- **AI Category**: {company['ai_category']}\n"
                f"- **Segment Tags**: {company['seg_tags']}\n"
                f"- **Presence**: {company['germany_presence']}\n"
                f"- **Company Type**: {company['company_type']}\n"
                f"- **AI Use Cases**: {company['use_cases']}\n"
                f"- **Top German Customers**: {company['customers']}\n"
                f"- **Funding**: {company['funding']}\n"
                f"- **Revenue**: {company['revenue']}\n"
                f"- **Maturity**: {company['maturity']}\n"
                f"- **Deployment Evidence**: {company['deployment_evidence']}\n"
                f"- **Website**: [{company['website']}](https://{company['website']})\n"
            )
            direct_context.append(company_text)
            sources.append({
                "type": "database_profile",
                "title": f"{company['name']} Directory Profile",
                "link": f"/#/company/{company['id']}"
            })
            
            # Fetch recent news for context
            news_items = cursor.execute("SELECT headline, source, publication_date, url, summary FROM news_items WHERE company_id = ? LIMIT 3", (company['id'],)).fetchall()
            for n in news_items:
                n_text = (
                    f"### NEWS FOR {company['name']}:\n"
                    f"- Headline: {n['headline']}\n"
                    f"- Source: {n['source']} ({n['publication_date']})\n"
                    f"- Summary: {n['summary']}\n"
                    f"- Link: {n['url']}"
                )
                direct_context.append(n_text)
                sources.append({
                    "type": "news_article",
                    "title": f"News: {n['headline']}",
                    "link": n['url']
                })
                
    # 2. Vector Context (FAISS Search)
    vector_results = search_index(query, k=6)
    vector_context = []
    
    for r in vector_results:
        item = r['item']
        # Avoid duplicate context if already added in direct lookup
        is_duplicate = False
        if item['type'] == 'company':
            for c in mentioned_companies:
                if c['id'] == item['id']:
                    is_duplicate = True
                    break
        if not is_duplicate:
            vector_context.append(f"### Chunk ({item['type'].upper()}): {item['name']}\n{item['text']}")
            
            # Add sources
            if item['type'] == 'company':
                sources.append({
                    "type": "database_profile",
                    "title": f"{item['name']} Profile",
                    "link": f"/#/company/{item['id']}"
                })
            elif item['type'] == 'problem':
                sources.append({
                    "type": "problem_statement",
                    "title": f"Problem: {item['name']}",
                    "link": f"/#/problems"
                })
            elif item['type'] == 'mapping':
                sources.append({
                    "type": "problem_mapping",
                    "title": f"ROI Mapping: {item['name']}",
                    "link": f"/#/problems"
                })
            elif item['type'] == 'news':
                # Get URL
                news_url = cursor.execute("SELECT url FROM news_items WHERE id = ?", (item['id'],)).fetchone()
                sources.append({
                    "type": "news_article",
                    "title": f"News: {item['name']}",
                    "link": news_url[0] if news_url else "#"
                })
                
    conn.close()
    
    # 3. Build Prompt
    context_str = "\n\n".join(direct_context + vector_context)
    
    prompt = (
        "You are 'Ask AI', the grounded intelligence assistant of the AI Atlas platform.\n"
        "Your task is to answer user queries using ONLY the verified context below. You must adhere to these rules:\n\n"
        "RULES:\n"
        "1. Round-Trip Fidelity: For any fact about a company's funding, revenue, maturity, customers, use cases, or deployment evidence, "
        "your answer must exactly match the values in the context. Do not invent or approximate.\n"
        "2. Grounding: Answer ONLY using facts present in the Context. If the information is not in the context, state: "
        "'I do not have this information in my knowledge base.' do not answer using general LLM knowledge or guess.\n"
        "3. Citations: When you make a claim, cite the source. For companies, link to their profile (e.g. `[GEA Group AG](/#/company/2)`). "
        "For news items, link to the article URL (e.g. `[Headline](URL)`).\n"
        "4. Output format: Synthesized, natural and direct response in professional English. Use Markdown tables or bullet lists for clarity where appropriate.\n\n"
        f"CONTEXT:\n{context_str}\n\n"
        f"USER QUERY: {query}\n\n"
        "YOUR GROUNDED RESPONSE:"
    )
    
    # Call Gemini
    model = genai.GenerativeModel("models/gemini-3.5-flash")
    response = model.generate_content(prompt)
    
    # Deduplicate sources based on link
    unique_sources = []
    seen_links = set()
    for s in sources:
        if s['link'] not in seen_links:
            seen_links.add(s['link'])
            unique_sources.append(s)
            
    return {
        "answer": response.text.strip(),
        "sources": unique_sources
    }
