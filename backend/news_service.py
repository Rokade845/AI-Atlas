import os
import requests
import xml.etree.ElementTree as ET
import urllib.parse
from datetime import datetime
import google.generativeai as genai
import json
from database import get_db_connection, add_news_item, get_processed_url, add_processed_url

# Local env loader helper
def load_env():
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

def is_gemini_available():
    global GEMINI_API_KEY
    load_env()
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    return bool(GEMINI_API_KEY)

def evaluate_article(company_name, headline, snippet):
    """Evaluate article relevance and generate summary in a single call to save Gemini Free Tier quota."""
    # 1. Deterministic pre-filtering (Free Tier optimization)
    clean_company = company_name.lower().replace(" ag", "").replace(" gmbh", "").replace(" se", "").replace("& co kg", "").strip()
    headline_lower = headline.lower()
    snippet_lower = snippet.lower() if snippet else ""
    
    # If clean name is not found anywhere in headline or snippet, discard immediately
    if clean_company not in headline_lower and clean_company not in snippet_lower:
        print(f"[{company_name}] Pre-filtered out article: {headline}")
        return {"is_relevant": False, "summary": "", "called_api": False}
    
    if not is_gemini_available():
        return {"is_relevant": True, "summary": snippet[:150] if snippet else "No summary available.", "called_api": False}
        
    prompt = (
        f"You are an AI market analyst evaluating news articles for relevance and summarizing them.\n"
        f"Company Name: {company_name}\n"
        f"We are looking for news specifically about this company, operating in food/beverage technology, processing machinery, packaging AI, food quality, or cold chain logistics.\n\n"
        f"News Article Details:\n"
        f"- Headline: {headline}\n"
        f"- Snippet: {snippet}\n\n"
        f"Task:\n"
        f"1. Determine if this article is directly about '{company_name}' and relevant to its business. (Beware of false matches/name collisions).\n"
        f"2. If it is relevant, generate a high-quality, professional, concise one-sentence summary (maximum 25 words).\n\n"
        f"Return a JSON object with keys:\n"
        f"- 'is_relevant': boolean\n"
        f"- 'explanation': string (1-sentence explanation of decision)\n"
        f"- 'summary': string (the summary if relevant; otherwise empty string)\n"
        f"Return ONLY valid JSON."
    )
    
    # Call Gemini with retry logic
    max_retries = 3
    base_delay = 10
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel("models/gemini-2.0-flash")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            res_text = response.text.strip()
            data = json.loads(res_text)
            return {
                "is_relevant": data.get("is_relevant", False),
                "summary": data.get("summary", ""),
                "called_api": True
            }
        except Exception as e:
            print(f"Gemini API attempt {attempt+1} failed for {company_name}: {e}")
            if attempt < max_retries - 1:
                import time
                sleep_time = base_delay * (2 ** attempt)
                print(f"Rate limited or error. Sleeping {sleep_time} seconds before retry...")
                time.sleep(sleep_time)
            else:
                return {"is_relevant": False, "summary": "", "called_api": True}

def fetch_news_for_company(company_id, max_results=3):
    """Fetch news for a company from Google News RSS, filter and save to DB."""
    conn = get_db_connection()
    company_row = conn.execute("SELECT name FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    
    if not company_row:
        return 0
        
    company_name = company_row['name']
    print(f"Fetching news for {company_name}...")
    
    search_query = f'"{company_name}" AND (AI OR food OR beverage OR technology OR processing)'
    encoded_query = urllib.parse.quote(search_query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    try:
        response = requests.get(rss_url, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch RSS for {company_name}: Status {response.status_code}")
            return 0
            
        root = ET.fromstring(response.content)
        items = root.findall(".//item")
        
        # Limit evaluation to the top 5 articles
        items_to_evaluate = items[:5]
        
        saved_count = 0
        import time
        
        for item in items_to_evaluate:
            if saved_count >= max_results:
                break
                
            headline = item.find("title").text
            url = item.find("link").text
            pub_date_str = item.find("pubDate").text
            source = item.find("source").text if item.find("source") is not None else "Google News"
            description_elem = item.find("description")
            description = description_elem.text if description_elem is not None else ""
            
            # Clean headline
            if " - " in headline:
                headline = headline.rsplit(" - ", 1)[0]
                
            try:
                dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
                pub_date = dt.strftime("%Y-%m-%d")
            except Exception:
                pub_date = pub_date_str
                
            # 1. Deduplication: Check if URL already exists
            conn = get_db_connection()
            exists = conn.execute("SELECT 1 FROM news_items WHERE url = ?", (url,)).fetchone()
            conn.close()
            
            if exists:
                continue
                
            # 2. Check processed_news_urls Cache (Free Tier Optimization)
            cached = get_processed_url(url)
            if cached is not None:
                is_relevant = cached["is_relevant"]
                summary = cached["summary"]
                print(f"Cached hit for URL: {url} -> Relevant: {is_relevant}")
            else:
                # 3. Relevance Filtering & Summarization combined (Gemini Call)
                eval_result = evaluate_article(company_name, headline, description)
                is_relevant = eval_result["is_relevant"]
                summary = eval_result["summary"]
                
                # Save to URL Cache
                add_processed_url(url, is_relevant, summary)
                
                # Free Tier Delay only on actual Gemini Call
                if eval_result.get("called_api", True):
                    time.sleep(5.0)
                    
            if not is_relevant:
                continue
                
            # 4. Save to DB
            news_id = add_news_item(company_id, headline, source, pub_date, summary, url)
            if news_id:
                saved_count += 1
                
        # Trigger RAG re-index if we added new items
        if saved_count > 0:
            print(f"Added {saved_count} new articles for {company_name}")
            from rag_service import build_faiss_index
            build_faiss_index()
            
        return saved_count
        
    except Exception as e:
        print(f"Error fetching news for {company_name}: {e}")
        return 0

def refresh_all_news(limit=10):
    """Fetch news for a random batch of companies to conserve API quota and avoid long runtimes."""
    conn = get_db_connection()
    companies = conn.execute("SELECT id, name FROM companies").fetchall()
    conn.close()
    
    if not companies:
        print("No companies to monitor.")
        return 0
        
    import random
    import time
    
    # Randomly select a batch of companies to monitor in this turn
    batch = random.sample(companies, min(limit, len(companies)))
    
    total_added = 0
    print(f"Starting background news refresh for batch of {len(batch)} companies...")
    for c in batch:
        try:
            added = fetch_news_for_company(c['id'], max_results=2)
            total_added += added
            # Sleep between company fetches to prevent rate limit spikes
            time.sleep(2.0)
        except Exception as e:
            print(f"Error in background update for {c['name']}: {e}")
            
    print(f"News refresh completed. Added a total of {total_added} articles.")
    return total_added
