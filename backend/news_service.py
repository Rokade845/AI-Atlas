import os
import requests
import xml.etree.ElementTree as ET
import urllib.parse
from datetime import datetime
import google.generativeai as genai
import json
from database import get_db_connection, add_news_item

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
                            if k and v and k not in os.environ:
                                os.environ[k] = v
            break

load_env()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def is_gemini_available():
    global GEMINI_API_KEY
    if not GEMINI_API_KEY:
        load_env()
        GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
    return bool(GEMINI_API_KEY)

def check_article_relevance(company_name, headline, description):
    """Use Gemini to determine if a news item is relevant to the specific company and not a false match."""
    if not is_gemini_available():
        # Fallback: simple case-insensitive substring search
        c_name_lower = company_name.lower().replace(" ag", "").replace(" gmbh", "").strip()
        headline_lower = headline.lower()
        desc_lower = description.lower() if description else ""
        return c_name_lower in headline_lower or c_name_lower in desc_lower
        
    prompt = (
        f"You are an AI analyst evaluating news relevancy.\n"
        f"Company Name: {company_name}\n"
        f"We are looking for news specifically about this company, which operates in the areas of "
        f"artificial intelligence, food/beverage technology, processing machinery, food quality, or cold chain logistics.\n\n"
        f"News Article Details:\n"
        f"- Headline: {headline}\n"
        f"- Snippet: {description}\n\n"
        f"Is this article directly about '{company_name}' and relevant to its business? "
        f"Beware of name collisions (e.g., general terms like 'picnic', or unrelated entities with similar names).\n"
        f"Return your decision in JSON format with keys:\n"
        f"- 'is_relevant': boolean\n"
        f"- 'explanation': string (brief, 1 sentence explaining decision)\n"
        f"Only return JSON."
    )
    
    try:
        model = genai.GenerativeModel("models/gemini-3.5-flash")
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text.strip())
        return data.get('is_relevant', False)
    except Exception as e:
        print(f"Relevance check error for {company_name}: {e}")
        # Default fallback to true if API fails, to ensure we don't block all news
        c_name_lower = company_name.lower().replace(" ag", "").replace(" gmbh", "").strip()
        return c_name_lower in headline.lower()

def generate_news_summary(company_name, headline, description):
    """Generate a high-quality one-sentence summary using Gemini."""
    if not is_gemini_available():
        return description[:150] if description else "No summary available."
        
    prompt = (
        f"Create a professional, concise one-sentence summary (max 25 words) for this news item about the company '{company_name}':\n"
        f"Headline: {headline}\n"
        f"Snippet: {description}\n"
        f"Summary:"
    )
    
    try:
        model = genai.GenerativeModel("models/gemini-3.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Summary generation error: {e}")
        return description[:150] if description else "No summary available."

def fetch_news_for_company(company_id, max_results=3):
    """Fetch news for a company from Google News RSS, filter and save to DB."""
    conn = get_db_connection()
    company_row = conn.execute("SELECT name FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    
    if not company_row:
        return 0
        
    company_name = company_row['name']
    print(f"Fetching news for {company_name}...")
    
    # We construct a query containing company name and sector keywords to focus results
    # We search for company name as a phrase, and keywords
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
        
        # Limit evaluation to the top 5 articles to conserve API quota
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
            
            # Clean headline (often ends with ' - Source Name')
            if " - " in headline:
                headline = headline.rsplit(" - ", 1)[0]
                
            # Convert pub_date_str (e.g. "Tue, 14 Jul 2026 12:00:00 GMT") to a cleaner format (YYYY-MM-DD)
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
                
            # 2. Relevance Filtering
            is_relevant = check_article_relevance(company_name, headline, description)
            time.sleep(1.5)  # Rate limit safety delay
            if not is_relevant:
                print(f"Skipping irrelevant article: {headline}")
                continue
                
            # 3. Generate Summary
            summary = generate_news_summary(company_name, headline, description)
            time.sleep(1.5)  # Rate limit safety delay
            
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

def refresh_all_news():
    """Fetch news for watchlisted companies only to conserve API quota."""
    conn = get_db_connection()
    # Query only watchlisted companies to avoid API quota issues
    companies = conn.execute("""
        SELECT c.id, c.name 
        FROM watchlist w
        JOIN companies c ON w.company_id = c.id
    """).fetchall()
    conn.close()
    
    if not companies:
        print("No companies in watchlist. Skipping automated news refresh.")
        return 0
        
    total_added = 0
    import time
    for c in companies:
        added = fetch_news_for_company(c['id'])
        total_added += added
        # Sleep between company fetches to prevent token exhaustion
        time.sleep(2)
        
    print(f"News refresh completed. Added a total of {total_added} articles.")
    return total_added
