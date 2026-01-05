import requests
import time
import json
import uuid

# Configuration
BASE_URL = "http://localhost:8000"
# Unique Tenant ID for this run
TENANT_ID = f"test-{str(uuid.uuid4())[:8]}"
HEADERS = {"Content-Type": "application/json"}

def log(message, status="INFO"):
    colors = {
        "INFO": "\033[94m",    # Blue
        "SUCCESS": "\033[92m", # Green
        "FAIL": "\033[91m",    # Red
        "RESET": "\033[0m"
    }
    print(f"{colors.get(status, '')}[{status}] {message}{colors['RESET']}")

def ingest_document(text, source):
    """Helper to upload a document as a file"""
    url = f"{BASE_URL}/ingest?tenant_id={TENANT_ID}"
    files = {
        'file': (f'{source}.txt', text, 'text/plain')
    }
    try:
        response = requests.post(url, files=files)
        if response.status_code == 200:
            return True
        else:
            log(f"Ingest failed: {response.text}", "FAIL")
            return False
    except Exception as e:
        log(f"Connection error: {str(e)}", "FAIL")
        return False

def query_rag(question, history=None, strategy="simple"): 
    url = f"{BASE_URL}/query" 
    payload = {
        "query": question,
        "tenant_id": TENANT_ID,
        "top_k": 5,
        "chat_history": history if history else [],
        "strategy": strategy 
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            log(f"Query failed ({response.status_code}): {response.text}", "FAIL")
            return {}
    except Exception as e:
        log(f"Connection error: {str(e)}", "FAIL")
        return {}

def cleanup_data():
    """Helper to delete tenant data"""
    url = f"{BASE_URL}/reset/{TENANT_ID}"
    try:
        response = requests.delete(url)
        if response.status_code == 200:
            log(f"Cleanup successful for tenant: {TENANT_ID}", "SUCCESS")
        else:
            log(f"Cleanup failed: {response.text}", "FAIL")
    except Exception as e:
        log(f"Cleanup connection error: {str(e)}", "FAIL")

def run_tests():
    log(f"--- STARTING RAG TESTS (Tenant: {TENANT_ID}) ---", "INFO")
    
    try:
        # GLOBAL WAIT
        time.sleep(2) 

        # ==========================================
        # SCENARIO 1: Vocabulary Mismatch
        # ==========================================
        log("Running Scenario 1: Vocabulary Mismatch...", "INFO")
        ingest_document(
            text="The partition tolerance of the system ensures continuous operation even when network links fail.", 
            source="doc-arch-v1"
        )
        time.sleep(2)
        
        response = query_rag("What happens if the connection drops?")
        results = response.get("results", [])
        
        if results:
            found_scen_1 = any("partition tolerance" in str(r) for r in results)
            if found_scen_1:
                log("Scenario 1 PASSED: Vector search bridged the vocabulary gap.", "SUCCESS")
            else:
                log("Scenario 1 FAILED: Documents found, but not the right one.", "FAIL")
        else:
            log("Scenario 1 FAILED: No results found.", "FAIL")

        # ==========================================
        # SCENARIO 2: Exact Keyword Override
        # ==========================================
        log("\nRunning Scenario 2: Exact Keyword Override...", "INFO")
        ingest_document("Error 500 happens when the server crashes.", "error-logs")
        ingest_document("Error 505 is a version not supported error.", "error-logs")
        time.sleep(2)
        
        response = query_rag("Error 505") 
        results = response.get("results", [])
        
        if not results:
            log("Scenario 2 FAILED: No results returned.", "FAIL")
        else:
            first_result = results[0]['content']
            if "Error 505" in first_result:
                log(f"Scenario 2 PASSED: Top result was '{first_result}'", "SUCCESS")
            else:
                log(f"Scenario 2 FAILED: Top result was '{first_result}' (Expected Error 505)", "FAIL")

        # ==========================================
        # SCENARIO 3: Conflicting Info
        # ==========================================
        log("\nRunning Scenario 3: Conflicting Information...", "INFO")
        ingest_document("Policy 2020: Refund window is 30 days.", "policy-old")
        ingest_document("Policy 2025: Refund window is 60 days.", "policy-new")
        time.sleep(2)
        
        response = query_rag("refund window duration")
        results = response.get("results", [])
        
        if results:
            content_blob = " ".join([r['content'] for r in results])
            if "30 days" in content_blob and "60 days" in content_blob:
                log("Scenario 3 PASSED: Retrieved both conflicting policies.", "SUCCESS")
            else:
                log("Scenario 3 FAILED: Did not retrieve both versions.", "FAIL")
        else:
            log("Scenario 3 FAILED: No results found.", "FAIL")

        # ==========================================
        # SCENARIO 4: Chat Memory
        # ==========================================
        log("\nRunning Scenario 4: Chat Context Rewriting...", "INFO")
        ingest_document("PostgreSQL is an open-source relational database system.", "tech-stack")
        time.sleep(2)
        
        history = [
            {"role": "user", "content": "What is the best database for structured data?"},
            {"role": "assistant", "content": "PostgreSQL is a great choice for structured data."}
        ]
        response_data = query_rag("How do I install it?", history=history)
        
        if "standalone_query" in response_data:
            rewritten = response_data["standalone_query"].lower()
            if "postgres" in rewritten or "database" in rewritten:
                log(f"Scenario 4 PASSED: Rewrote 'it' to '{response_data['standalone_query']}'", "SUCCESS")
            else:
                log(f"Scenario 4 FAILED: Rewrote to '{rewritten}'", "FAIL")
        else:
            log("Scenario 4 FAILED: API did not return 'standalone_query' field.", "FAIL")

        # ==========================================
        # SCENARIO 5: Irrelevant/Negative Query
        # ==========================================
        log("\nRunning Scenario 5: Irrelevant Query...", "INFO")
        response = query_rag("How do I bake a chocolate cake?")
        results = response.get("results", [])
        
        if len(results) == 0:
            log("Scenario 5 PASSED: Correctly returned no results.", "SUCCESS")
        else:
            log("Scenario 5 WARNING: Returned results for 'chocolate cake'. Check distance threshold.", "FAIL")

        # ==========================================
        # SCENARIO 6: Multi-Query Expansion
        # ==========================================
        log("\nRunning Scenario 6: Multi-Query Expansion...", "INFO")
        response = query_rag("Deployment options for the database", strategy="multi_query")
        gen_queries = response.get("generated_queries", [])
        if len(gen_queries) > 1:
            log(f"Scenario 6 PASSED: Generated {len(gen_queries)} variations.", "SUCCESS")
        else:
            log("Scenario 6 FAILED: Did not generate multiple queries.", "FAIL")

        # ==========================================
        # SCENARIO 7: Decomposition
        # ==========================================
        log("\nRunning Scenario 7: Decomposition...", "INFO")
        response = query_rag("Compare Policy 2020 vs Policy 2025", strategy="decomposition")
        gen_queries = response.get("generated_queries", [])
        if len(gen_queries) >= 2:
            log(f"Scenario 7 PASSED: Decomposed into {len(gen_queries)} sub-questions.", "SUCCESS")
        else:
            log("Scenario 7 FAILED: Failed to decompose complex query.", "FAIL")

        # ==========================================
        # SCENARIO 8: HyDE
        # ==========================================
        log("\nRunning Scenario 8: HyDE...", "INFO")
        response = query_rag("database installation", strategy="hyde")
        gen_queries = response.get("generated_queries", [])
        if gen_queries and len(gen_queries[0]) > 20:
            log(f"Scenario 8 PASSED: Generated hypothetical document.", "SUCCESS")
        else:
            log("Scenario 8 FAILED: Did not generate a hypothetical answer.", "FAIL")

    except Exception as e:
        log(f"CRITICAL TEST FAILURE: {e}", "FAIL")
        
    finally:
        log("\n--- CLEANING UP ---", "INFO")
        cleanup_data()
        log("--- TEST RUN COMPLETE ---", "INFO")

if __name__ == "__main__":
    run_tests()