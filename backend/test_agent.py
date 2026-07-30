import os
import sys

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import database
import rag_service
import news_service
import discovery_service

def test_agent_local_grounding():
    print("\n=== Test 1: Local Knowledge Base Grounding ===")
    query = "What is the estimated revenue and maturity of GEA Group AG?"
    res = rag_service.ask_ai(query)
    
    print(f"Query: {query}")
    print(f"Steps: {res.get('steps')}")
    print(f"Sources: {res.get('sources')}")
    print(f"Answer: {res.get('answer')}")
    
    # Assertions
    assert len(res.get('steps', [])) > 0, "Agent should have taken at least one step."
    local_called = any(step.get('action') == 'query_local_knowledge_base' for step in res.get('steps', []))
    assert local_called, "Agent should have queried the local knowledge base."
    print("Test 1 PASSED!")

def test_agent_general_query():
    print("\n=== Test 2: General Query / Web Search ===")
    query = "Briefly explain the role of AI in aerospace manufacturing in general."
    res = rag_service.ask_ai(query)
    
    print(f"Query: {query}")
    print(f"Steps: {res.get('steps')}")
    print(f"Sources: {res.get('sources')}")
    print(f"Answer: {res.get('answer')}")
    
    # Assertions
    assert len(res.get('steps', [])) > 0, "Agent should have taken at least one step."
    web_called = any(step.get('action') == 'query_web_search' for step in res.get('steps', []))
    assert web_called, "Agent should have queried the web for general information."
    print("Test 2 PASSED!")

def test_news_pre_filtering_and_cache():
    print("\n=== Test 3: News Pre-Filtering and Cache ===")
    # GEA Group AG exists
    company_name = "GEA Group AG"
    headline_matched = "GEA Group launches new AI sorting technology for dairy"
    headline_mismatched = "Apple releases new iPhone 18 Pro Max"
    
    # 1. Test Match (should evaluate or hit mock)
    eval_match = news_service.evaluate_article(company_name, headline_matched, "A snippet about GEA Group's new AI.")
    print(f"Match Eval: {eval_match}")
    
    # 2. Test Mismatch (should pre-filter instantly without Gemini API call)
    eval_mismismatch = news_service.evaluate_article(company_name, headline_mismatched, "A snippet about Apple's new phone.")
    print(f"Mismatch Eval: {eval_mismismatch}")
    assert eval_mismismatch["is_relevant"] is False
    assert eval_mismismatch["called_api"] is False, "Mismatched article should be pre-filtered without API call."
    
    print("Test 3 PASSED!")

if __name__ == "__main__":
    database.init_db()
    # Build FAISS index in-memory
    rag_service.build_faiss_index()
    
    try:
        test_agent_local_grounding()
        test_agent_general_query()
        test_news_pre_filtering_and_cache()
        print("\nAll agent verification tests PASSED successfully!")
    except AssertionError as ae:
        print(f"\nVerification failed: {ae}")
        sys.exit(1)
