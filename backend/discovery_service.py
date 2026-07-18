import os
import json
import google.generativeai as genai
from google.generativeai import types
from database import get_sectors

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

def discover_companies(sector, country):
    """Researches companies using Gemini Google Search grounding and returns structured candidates."""
    if not is_gemini_available():
        return {
            "success": False,
            "error": "GEMINI_API_KEY is not configured in backend/.env file."
        }
        
    # Get standard sectors from DB to help mapping
    sectors = get_sectors()
    sectors_info = "\n".join([f"ID {s['id']}: {s['name']} - {s['definition']}" for s in sectors])
    
    prompt = (
        f"You are a professional market intelligence analyst researching AI deployment in the food and beverage industry.\n"
        f"Your task is to identify and profile exactly 3 REAL and VERIFIABLE companies that solve problems using AI in the sector '{sector}' within or serving the country '{country}'.\n\n"
        f"CRITICAL WARNING:\n"
        f"Do NOT invent or hallucinate companies. Every company returned must have active websites and clear web proof of existence. "
        f"Provide the exact sources and URLs of where you found the information. If you cannot find at least 3, only return the ones you can verify.\n\n"
        f"Available Sector IDs for mapping ('seg_tags'):\n{sectors_info}\n\n"
        f"Return the results in a structured JSON format containing a list of candidates. "
        f"Each candidate must have the following fields:\n"
        f"- 'name': Company Name (e.g. 'GEA Group AG')\n"
        f"- 'country': Core headquarters country (e.g. 'Germany')\n"
        f"- 'ai_category': Clean summary of their AI application category (e.g. 'Food Sorting AI' or 'CIP Process Optimization')\n"
        f"- 'seg_tags': A comma-separated string of Sector IDs from the list above that this company solves problems for (e.g. '1,9')\n"
        f"- 'germany_presence': Description of their presence in Germany (e.g. 'LOCAL HQ — Düsseldorf' or 'EUROPEAN PRESENCE' or 'Global supplier')\n"
        f"- 'company_type': 'Incumbent' or 'NewCo'\n"
        f"- 'use_cases': Bullet points describing their AI use cases (e.g. 'AI sorting machine, yield optimization')\n"
        f"- 'customers': Identified German customers, or 'Unknown' if not found (e.g. 'Müller Dairy')\n"
        f"- 'funding': Funding description (e.g. 'Public (MDAX)', 'Private family business', 'Series B ($20M)', 'Unknown')\n"
        f"- 'revenue': Estimated annual revenue (e.g. '€5.3B', '$15M+', 'Unknown')\n"
        f"- 'maturity': Maturity tag (e.g. '4 — Mature' or '3 — Scaling' or '2 — Emerging')\n"
        f"- 'deployment_evidence': Verified deployment evidence description (e.g. 'Implemented AI sorting at German potato plant, reducing waste by 25%')\n"
        f"- 'website': Website domain (e.g. 'company.com')\n"
        f"- 'confidence': Confidence level: 'High', 'Medium', or 'Low'\n"
        f"- 'evidence': A list of source objects, each with 'source_url' (absolute link starting with http) and 'snippet' (verbatim quote or detail showing proof of the company and its AI use case)\n\n"
        f"Return the final output ONLY as a valid JSON object matching this schema:\n"
        f"{{\n"
        f"  \"candidates\": [\n"
        f"    ... candidates matching the above model ...\n"
        f"  ]\n"
        f"}}\n"
    )
    
    try:
        # Construct the protobuf Tool object directly to bypass legacy SDK validation
        google_search_tool = types.protos.Tool(
            google_search=types.protos.Tool.GoogleSearch()
        )
        
        model = genai.GenerativeModel(
            model_name="models/gemini-2.5-flash",
            tools=[google_search_tool]
        )
        
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        raw_text = response.text.strip()
        
        # Parse the JSON response
        data = json.loads(raw_text)
        return {
            "success": True,
            "candidates": data.get("candidates", [])
        }
        
    except Exception as e:
        print(f"Company discovery failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
