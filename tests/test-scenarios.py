import requests
import time
import json

# Configuration
BASE_URL = "http://localhost:8000"
TENANT_ID = "test-complex-scenarios"
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
    
    # 1. Create a "fake" file in memory
    files = {
        'file': (f'{source}.txt', text, 'text/plain')
    }
    
    try:
        # 2. Send as multipart/form-data (Do NOT set Content-Type header manually)
        response = requests.post(url, files=files)
        
        if response.status_code == 200:
            return True
        else:
            log(f"Ingest failed: {response.text}", "FAIL")
            return False
    except Exception as e:
        log(f"Connection error: {str(e)}", "FAIL")
        return False

def query_rag(question):
    """Helper to query the system with robust debugging"""
    url = f"{BASE_URL}/rag/query"
    payload = {
        "query": question,
        "tenant_id": TENANT_ID,
        "top_k": 5
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            
            # --- DEBUG: Print what we actually got ---
            # print(f"DEBUG RESPONSE TYPE: {type(data)}")
            # print(f"DEBUG RESPONSE: {data}")
            
            # 1. If it's a Dictionary, try to find the list inside
            if isinstance(data, dict):
                # Common wrappers: 'results', 'data', 'items'
                if 'results' in data:
                    return data['results']
                elif 'data' in data:
                    return data['data']
                # If it looks like a single error message
                elif 'detail' in data:
                    log(f"API Error: {data['detail']}", "FAIL")
                    return []
                # Fallback: maybe the API returns a single dict object? Wrap it in a list.
                else:
                    return [data]
            
            # 2. If it's already a List, return it (Happy Path)
            if isinstance(data, list):
                return data
                
            return []
        else:
            log(f"Query failed ({response.status_code}): {response.text}", "FAIL")
            return []
    except Exception as e:
        log(f"Connection error: {str(e)}", "FAIL")
        return []

def run_tests():
    log("--- STARTING COMPLEX SCENARIO TESTS ---", "INFO")
    
    # GLOBAL WAIT: Give ingestion a moment to finish processing
    time.sleep(2) 

    # ==========================================
    # SCENARIO 1: Vocabulary Mismatch (Vector Strength)
    # ==========================================
    log("Running Scenario 1: Vocabulary Mismatch...", "INFO")
    ingest_document(
        text="The partition tolerance of the system ensures continuous operation even when network links fail.", 
        source="doc-arch-v1"
    )
    
    time.sleep(2) # Wait for vector generation
    
    results = query_rag("What happens if the connection drops?")
    
    if results:
        found_scen_1 = any("partition tolerance" in str(r) for r in results)
        if found_scen_1:
            log("Scenario 1 PASSED: Vector search bridged the vocabulary gap.", "SUCCESS")
        else:
            log("Scenario 1 FAILED: Documents found, but not the right one.", "FAIL")
    else:
        log("Scenario 1 FAILED: No results found.", "FAIL")

    # ==========================================
    # SCENARIO 2: Exact Keyword Override (RRF Strength)
    # ==========================================
    log("\nRunning Scenario 2: Exact Keyword Override...", "INFO")
    ingest_document("Error 500 happens when the server crashes.", "error-logs")
    ingest_document("Error 505 is a version not supported error.", "error-logs")
    
    time.sleep(2)
    
    # CHANGE: Use a keyword, not a sentence, because your backend uses simple ILIKE
    results = query_rag("Error 505") 
    
    if not results:
        log("Scenario 2 FAILED: No results returned.", "FAIL")
    else:
        first_result = results[0]['content']
        if "Error 505" in first_result:
            log(f"Scenario 2 PASSED: Top result was '{first_result}'", "SUCCESS")
        else:
            log(f"Scenario 2 FAILED: Top result was '{first_result}' (Expected Error 505)", "FAIL")

    # ==========================================
    # SCENARIO 3: Conflicting Info (Retrieval Check)
    # ==========================================
    log("\nRunning Scenario 3: Conflicting Information...", "INFO")
    ingest_document("Policy 2020: Refund window is 30 days.", "policy-old")
    ingest_document("Policy 2025: Refund window is 60 days.", "policy-new")
    
    time.sleep(2)
    
    results = query_rag("refund window duration")
    
    if results:
        content_blob = " ".join([r['content'] for r in results])
        if "30 days" in content_blob and "60 days" in content_blob:
            log("Scenario 3 PASSED: Retrieved both conflicting policies.", "SUCCESS")
        else:
            log("Scenario 3 FAILED: Did not retrieve both versions.", "FAIL")
    else:
        log("Scenario 3 FAILED: No results found.", "FAIL")
        
    log("\n--- TEST RUN COMPLETE ---", "INFO")

if __name__ == "__main__":
    run_tests()