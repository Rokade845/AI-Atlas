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
                            if k and v:
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

def query_local_knowledge_base(search_query: str) -> str:
    """Useful to search local database records and FAISS vector index for information about companies, sectors, problems, and ROI benchmarks."""
    mentioned_companies = extract_mentioned_companies(search_query)
    direct_context = []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for c in mentioned_companies:
        company_row = cursor.execute("SELECT * FROM companies WHERE id = ?", (c['id'],)).fetchone()
        if company_row:
            company = dict(company_row)
            company_text = (
                f"### COMPANY PROFILE: {company['name']} (ID: {company['id']})\n"
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
                f"- **Confidence Score**: {company.get('confidence_score', 100)}%\n"
                f"- **Ingestion Source**: {company.get('ingestion_source', 'CSV Seed')}\n"
            )
            direct_context.append(company_text)
            
            # Fetch recent news
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
                
    # Vector Context
    vector_results = search_index(search_query, k=6)
    vector_context = []
    
    for r in vector_results:
        item = r['item']
        is_duplicate = False
        if item['type'] == 'company':
            for c in mentioned_companies:
                if c['id'] == item['id']:
                    is_duplicate = True
                    break
        if not is_duplicate:
            vector_context.append(f"### Chunk ({item['type'].upper()}): {item['name']}\n{item['text']}")
            
    conn.close()
    
    context_str = "\n\n".join(direct_context + vector_context)
    return context_str if context_str else "No relevant information found in the local knowledge base."

def query_web_search(search_query: str) -> str:
    """Useful to search the web for recent news, articles, and general information outside the local database."""
    if not get_gemini_client():
        return "Gemini API key not configured."
        
    try:
        from google.generativeai import types
        google_search_tool = types.protos.Tool(
            google_search=types.protos.Tool.GoogleSearch()
        )
        model = genai.GenerativeModel(
            model_name="models/gemini-2.0-flash",
            tools=[google_search_tool]
        )
        prompt = (
            f"You are a web search assistant. Search the web for information regarding: '{search_query}'.\n"
            f"Provide a summary of the facts found, along with citations and URLs. Be objective and concise."
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Web search tool execution failed: {e}")
        return f"Error executing web search: {e}"

def trigger_company_discovery(sector: str, country: str = "Germany") -> str:
    """Useful to discover and profile new AI companies in a specific sector and country. High confidence candidates are automatically saved to the database."""
    try:
        from discovery_service import run_auto_discovery
        count = run_auto_discovery(sector, country)
        return (
            f"Completed automated company discovery for sector '{sector}' in country '{country}'. "
            f"Found and automatically ingested {count} new companies with confidence >= 90% into the database. "
            f"The vector index was rebuilt, and these companies are now queryable."
        )
    except Exception as e:
        print(f"Auto discovery tool execution failed: {e}")
        return f"Error running auto company discovery: {e}"

def ask_ai(query):
    """Answer natural language queries using a reasoning agent loop with tools."""
    if not get_gemini_client():
        return {
            "answer": "Gemini API key is not configured. Please set the `GEMINI_API_KEY` in the `backend/.env` file.",
            "sources": [],
            "steps": []
        }
        
    # Map of tools
    tool_map = {
        "query_local_knowledge_base": query_local_knowledge_base,
        "query_web_search": query_web_search,
        "trigger_company_discovery": trigger_company_discovery
    }
    
    # Pre-retrieve local database context to optimize API requests
    local_context = query_local_knowledge_base(query)
    
    # Initialize steps with the pre-retrieved query to ensure test assertion compatibility and UI tracking
    steps = [{
        "action": "query_local_knowledge_base",
        "detail": "Pre-retrieved local database and vector store context to minimize LLM API requests.",
        "args": {"search_query": query}
    }]
    
    system_instruction = (
        "You are 'Ask AI', the advanced agentic intelligence assistant of the AI Atlas platform.\n"
        "You help users analyze companies, F&B sectors, problems, and ROI benchmarks.\n"
        "You have access to tools to search the local database/vector store, search the web, or trigger company discovery.\n\n"
        "LOCAL KNOWLEDGE BASE CONTEXT:\n"
        f"{local_context}\n\n"
        "CRITICAL RULES:\n"
        "1. Exact Row Grounding: For specific profile attributes of database companies (funding, revenue, maturity, website, customers, use cases), "
        "your final answer must match database values with 100% round-trip fidelity. Do not invent or approximate.\n"
        "2. Use Preloaded Context First: We have already pre-retrieved the local knowledge base context above. "
        "If the user query can be fully answered using this local context, you MUST answer it immediately in your first response without calling any tools. "
        "Only call tools like `query_web_search` or `trigger_company_discovery` if the required information is not present in the preloaded context.\n"
        "3. General Knowledge / Web Search: If the query is general or refers to companies/facts not in the local database and not in the preloaded context, "
        "use `query_web_search` to find relevant info. Clearly mention that the answer is based on external web research.\n"
        "4. Action Execution: If the user asks you to discover new companies, find new startups, or scan a new sector, "
        "call `trigger_company_discovery` to run the discovery engine. Summarize what companies were automatically ingested vs ignored.\n"
        "5. Citations: Always provide markdown links. For companies in our database, format as `[Company Name](/#/company/ID)` (e.g. `[GEA Group AG](/#/company/2)`). "
        "For news or web links, cite their exact URLs.\n"
        "6. Professional Presentation: Synthesize answers clearly in professional English. Use tables/bullet points for comparative parameters."
    )
    
    from google.generativeai.types import content_types
    
    # Initialize conversation history
    chat_history = [
        {"role": "user", "parts": [query]}
    ]
    
    max_iterations = 5
    
    for i in range(max_iterations):
        try:
            model = genai.GenerativeModel(
                model_name="models/gemini-2.0-flash",
                tools=list(tool_map.values()),
                system_instruction=system_instruction
            )
            
            response = model.generate_content(chat_history)
            
            # Record assistant content
            content = response.candidates[0].content
            chat_history.append(content)
            
            # Find function calls
            function_calls = []
            for part in content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    function_calls.append(part.function_call)
                    
            if not function_calls:
                # No more function calls, agent is finished!
                break
                
            response_parts = []
            for call in function_calls:
                name = call.name
                args = dict(call.args)
                
                # Check if we should skip logging query_local_knowledge_base if we already pre-retrieved it,
                # but if the model generated it again, we execute it anyway and log it.
                step_detail = f"Invoked `{name}` with arguments: {json.dumps(args)}"
                print(step_detail)
                
                steps.append({
                    "action": name,
                    "detail": step_detail,
                    "args": args
                })
                
                if name in tool_map:
                    try:
                        result = tool_map[name](**args)
                    except Exception as e:
                        result = f"Error executing tool: {e}"
                else:
                    result = f"Error: Tool '{name}' not found."
                    
                response_parts.append(
                    content_types.to_part(
                        content_types.protos.Part(
                            function_response=content_types.protos.FunctionResponse(
                                name=name,
                                response={"result": result}
                            )
                        )
                    )
                )
                
            chat_history.append({
                "role": "user",
                "parts": response_parts
            })
            
            # Simple safety sleep for Gemini free tier
            import time
            time.sleep(1.0)
            
        except Exception as ex:
            print(f"Agent loop error: {ex}")
            break
            
    final_answer = ""
    # Look back for the final text response from the model
    # We scan chat history backwards to find the last assistant message
    for msg in reversed(chat_history):
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "")
        if role == "model":
            parts_text = []
            parts = msg.get("parts") if isinstance(msg, dict) else getattr(msg, "parts", [])
            for p in parts:
                text = p.get("text") if isinstance(p, dict) else getattr(p, "text", "")
                if text:
                    parts_text.append(text)
            if parts_text:
                final_answer = "\n".join(parts_text)
                break
                
    if not final_answer:
        # Fallback if chat_history check failed, with safe checks to prevent ValueError
        has_text = False
        if 'response' in locals() and response:
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    content = response.candidates[0].content
                    if hasattr(content, "parts") and content.parts:
                        for p in content.parts:
                            if hasattr(p, "text") and p.text:
                                has_text = True
                                break
            except Exception:
                pass
        
        if has_text:
            try:
                final_answer = response.text.strip()
            except Exception:
                final_answer = "The AI assistant is temporarily rate-limited or quota exceeded. Please wait a minute and try again."
        else:
            final_answer = "The AI assistant is temporarily rate-limited or quota exceeded. Please wait a minute and try again."
        
    # Extract sources:
    sources = []
    # 1. Direct match database references
    mentioned_companies = extract_mentioned_companies(query)
    seen_links = set()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    for c in mentioned_companies:
        link = f"/#/company/{c['id']}"
        if link not in seen_links:
            seen_links.add(link)
            sources.append({
                "type": "database_profile",
                "title": f"{c['name']} Profile",
                "link": link
            })
            
        # Also grab their news items
        news_items = cursor.execute("SELECT headline, url FROM news_items WHERE company_id = ? LIMIT 2", (c['id'],)).fetchall()
        for n in news_items:
            if n['url'] not in seen_links:
                seen_links.add(n['url'])
                sources.append({
                    "type": "news_article",
                    "title": f"News: {n['headline']}",
                    "link": n['url']
                })
    conn.close()
    
    # 2. Extract external links from response text
    import re
    links = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', final_answer)
    for title, url in links:
        if url not in seen_links:
            seen_links.add(url)
            sources.append({
                "type": "web_link",
                "title": title,
                "link": url
            })
            
    return {
        "answer": final_answer,
        "sources": sources,
        "steps": steps
    }
